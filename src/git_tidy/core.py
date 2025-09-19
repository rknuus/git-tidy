"""Git history tidy up script core functionality.

E.g. reorders commits to group those with similar file changes while preserving relative order within each group.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Optional, TypedDict


class CommitInfo(TypedDict):
    sha: str
    subject: str
    files: set[str]


class GitTidy:
    def __init__(self) -> None:
        self.original_branch: Optional[str] = None
        self.original_head: Optional[str] = None
        self.backup_branch: Optional[str] = None

    def run_git(
        self,
        cmd: list[str],
        check_output: bool = True,
        env: Optional[dict[str, str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run git command with error handling."""
        try:
            result = subprocess.run(
                ["git"] + cmd,
                capture_output=True,
                text=True,
                check=check_output,
                env=env,
            )
            return result
        except subprocess.CalledProcessError as e:
            raise GitError(
                f"Git command failed: {' '.join(cmd)}\nError: {e.stderr}"
            ) from e

    def create_backup(self) -> None:
        """Create a backup branch at current HEAD."""
        self.original_branch = self.run_git(["branch", "--show-current"]).stdout.strip()
        self.original_head = self.run_git(["rev-parse", "HEAD"]).stdout.strip()
        self.backup_branch = f"backup-{self.original_head[:8]}"

        self.run_git(["branch", self.backup_branch, "HEAD"])
        print(f"Created backup branch: {self.backup_branch}")

    def restore_from_backup(self) -> None:
        """Restore to original state if something goes wrong."""
        if self.backup_branch and self.original_head:
            print("Restoring from backup due to error...")

            # Check if we're in the middle of a rebase and abort it first
            try:
                status_result = self.run_git(
                    ["status", "--porcelain=v1"], check_output=False
                )
                if status_result.returncode == 0:
                    # Check if rebase is in progress
                    rebase_head_path = ".git/REBASE_HEAD"
                    if os.path.exists(rebase_head_path):
                        print("Aborting incomplete rebase...")
                        self.run_git(["rebase", "--abort"], check_output=False)
            except GitError:
                # If status check fails, continue with reset anyway
                pass

            self.run_git(["reset", "--hard", self.original_head])
            self.run_git(["branch", "-D", self.backup_branch], check_output=False)

    def cleanup_backup(self) -> None:
        """Clean up backup branch after successful operation."""
        if self.backup_branch:
            self.run_git(["branch", "-D", self.backup_branch], check_output=False)
            print(f"Cleaned up backup branch: {self.backup_branch}")

    def _determine_base_commit(self) -> str:
        """Determine the base commit for reordering."""
        # Get current branch name
        try:
            current_branch = self.run_git(["branch", "--show-current"]).stdout.strip()
        except GitError:
            current_branch = ""

        # If we're on main/master, use recent commits
        if current_branch in ["main", "master"] or not current_branch:
            # Use the last 10 commits, but ensure we don't go beyond repository root
            try:
                # Check how many commits we have
                commit_count_result = self.run_git(["rev-list", "--count", "HEAD"])
                commit_count = int(commit_count_result.stdout.strip())

                # Use at most 10 commits or all commits if fewer
                commits_to_use = min(10, commit_count)
                if commits_to_use <= 1:
                    # Not enough commits to reorder
                    return "HEAD"

                return f"HEAD~{commits_to_use - 1}"
            except (GitError, ValueError):
                return "HEAD"
        else:
            # Try to find merge base with main/master for feature branches
            for main_branch in ["main", "master", "origin/main", "origin/master"]:
                try:
                    base_ref = self.run_git(["merge-base", "HEAD", main_branch]).stdout.strip()
                    # Verify this isn't HEAD itself (which means we're on main)
                    head_sha = self.run_git(["rev-parse", "HEAD"]).stdout.strip()
                    if base_ref != head_sha:
                        return base_ref
                except GitError:
                    continue

            # Fallback to recent commits
            try:
                commit_count_result = self.run_git(["rev-list", "--count", "HEAD"])
                commit_count = int(commit_count_result.stdout.strip())
                commits_to_use = min(10, commit_count)
                if commits_to_use <= 1:
                    return "HEAD"
                return f"HEAD~{commits_to_use - 1}"
            except (GitError, ValueError):
                return "HEAD"

    def get_commits_to_rebase(self, base_ref: Optional[str] = None) -> list[CommitInfo]:
        """Get list of commits to reorder."""
        if base_ref is None:
            base_ref = self._determine_base_commit()

        # Get commit range
        commit_range = f"{base_ref}..HEAD"
        result = self.run_git(
            ["log", commit_range, "--pretty=format:%H|%s", "--reverse"]  # Oldest first
        )

        commits: list[CommitInfo] = []
        for line in result.stdout.strip().split("\n"):
            if line:
                sha, subject = line.split("|", 1)
                commit_info: CommitInfo = {
                    "sha": sha,
                    "subject": subject,
                    "files": self.get_commit_files(sha),
                }
                commits.append(commit_info)

        return commits

    def get_commit_files(self, sha: str) -> set[str]:
        """Get set of files changed in a commit."""
        result = self.run_git(["show", "--name-only", "--pretty=format:", sha])
        files = {
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        }
        return files

    def get_commit_message(self, sha: str) -> str:
        """Get the full commit message for a commit."""
        result = self.run_git(["show", "--pretty=format:%B", "--no-patch", sha])
        return result.stdout.strip()

    def calculate_similarity(self, files1: set[str], files2: set[str]) -> float:
        """Calculate Jaccard similarity between two sets of files."""
        if not files1 and not files2:
            return 1.0
        if not files1 or not files2:
            return 0.0

        intersection = len(files1.intersection(files2))
        union = len(files1.union(files2))
        return intersection / union if union > 0 else 0.0

    def group_commits(
        self, commits: list[CommitInfo], similarity_threshold: float = 0.3
    ) -> list[list[CommitInfo]]:
        """Group commits based on file similarity using a greedy approach."""
        if not commits:
            return []

        groups = []
        used = set()

        for i, commit in enumerate(commits):
            if i in used:
                continue

            # Start new group with this commit
            current_group = [commit]
            used.add(i)

            # Find similar commits that come later
            for j in range(i + 1, len(commits)):
                if j in used:
                    continue

                # Check similarity with any commit in current group
                max_similarity = max(
                    self.calculate_similarity(commit["files"], commits[j]["files"])
                    for commit in current_group
                )

                if max_similarity >= similarity_threshold:
                    current_group.append(commits[j])
                    used.add(j)

            groups.append(current_group)

        return groups

    def create_rebase_todo(self, groups: list[list[CommitInfo]]) -> str:
        """Create interactive rebase todo list."""
        todo_lines = []

        for group_idx, group in enumerate(groups):
            if group_idx > 0:
                todo_lines.append(
                    f"# Group {group_idx + 1}: {self.describe_group(group)}"
                )

            for _commit_idx, commit in enumerate(group):
                action = "pick"
                todo_lines.append(f"{action} {commit['sha'][:8]} {commit['subject']}")

        return "\n".join(todo_lines)

    def describe_group(self, group: list[CommitInfo]) -> str:
        """Create a description for a group of commits."""
        all_files = set()
        for commit in group:
            all_files.update(commit["files"])

        if len(all_files) <= 3:
            return f"Files: {', '.join(sorted(all_files))}"
        else:
            sample_files = sorted(all_files)[:3]
            return f"Files: {', '.join(sample_files)} and {len(all_files) - 3} more"

    def perform_rebase(self, groups: list[list[CommitInfo]], no_prompt: bool = False) -> bool:
        """Perform the actual rebase operation."""
        if len(groups) <= 1:
            print("No grouping needed - commits are already optimally ordered")
            return True

        # Create todo file
        todo_content = self.create_rebase_todo(groups)

        # Get base commit
        first_commit_sha = groups[0][0]["sha"]
        base_commit = self.run_git(["rev-parse", f"{first_commit_sha}^"]).stdout.strip()

        print(
            f"Rebasing {sum(len(g) for g in groups)} commits into {len(groups)} groups..."
        )
        print("\nProposed grouping:")
        for i, group in enumerate(groups):
            print(
                f"  Group {i + 1}: {len(group)} commits - {self.describe_group(group)}"
            )

        # Confirm with user
        if not no_prompt:
            response = input("\nProceed with rebase? (y/N): ")
            if response.lower() != "y":
                print("Rebase cancelled")
                return False

        # Write todo to temporary file and start interactive rebase
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(todo_content)
            todo_file = f.name

        try:
            # Set up environment for non-interactive rebase
            env = os.environ.copy()
            env["GIT_SEQUENCE_EDITOR"] = f"cp {todo_file}"

            result = self.run_git(
                ["rebase", "-i", base_commit], check_output=False, env=env
            )

            if result.returncode != 0:
                print(f"Rebase failed: {result.stderr}")
                return False

            print("Rebase completed successfully!")
            return True

        finally:
            os.unlink(todo_file)

    def perform_split_rebase(self, commits: list[CommitInfo], no_prompt: bool = False) -> bool:
        """Perform the actual split rebase operation."""
        # Check if any commits need splitting
        needs_splitting = any(len(commit["files"]) > 1 for commit in commits)
        if not needs_splitting:
            print("No commits need splitting - all commits already have single files")
            return True

        # Get base commit
        first_commit_sha = commits[0]["sha"]
        base_commit = self.run_git(["rev-parse", f"{first_commit_sha}^"]).stdout.strip()

        total_files = sum(len(commit["files"]) for commit in commits)
        print(
            f"Splitting {len(commits)} commits into {total_files} file-based commits..."
        )
        print("\nProposed splitting:")
        for commit in commits:
            if len(commit["files"]) > 1:
                print(
                    f"  Commit {commit['sha'][:8]}: {len(commit['files'])} files -> {len(commit['files'])} commits"
                )
                for file in sorted(commit["files"]):
                    print(f"    - split off {file}")
            else:
                print(
                    f"  Commit {commit['sha'][:8]}: {len(commit['files'])} file -> keep as-is"
                )

        # Confirm with user
        if not no_prompt:
            response = input("\nProceed with split rebase? (y/N): ")
            if response.lower() != "y":
                print("Split rebase cancelled")
                return False

        # Reset to base commit
        print(f"Resetting to base commit {base_commit[:8]}...")
        self.run_git(["reset", "--soft", base_commit])

        # Create new commits for each file
        new_commits = []
        for commit in commits:
            files = sorted(commit["files"])
            original_message = self.get_commit_message(commit["sha"])

            if len(files) <= 1:
                # Single file or no files - create commit as-is
                if files:
                    # Cherry-pick the commit to get the changes
                    self.run_git(["cherry-pick", "--no-commit", commit["sha"]])
                    # Reset and add only the specific file
                    self.run_git(["reset", "HEAD"])
                    self.run_git(["add", files[0]])
                    self.run_git(["commit", "-m", original_message])
                    new_commits.append(original_message)
                else:
                    # Empty commit - just commit with message
                    self.run_git(["commit", "--allow-empty", "-m", original_message])
                    new_commits.append(original_message)
            else:
                # Multiple files - create separate commits for each file
                for file in files:
                    # Cherry-pick the commit to get the changes
                    self.run_git(["cherry-pick", "--no-commit", commit["sha"]])
                    # Reset and add only the specific file
                    self.run_git(["reset", "HEAD"])
                    self.run_git(["add", file])
                    # Create commit with split message
                    split_message = f"split off {file}\n\n{original_message}"
                    self.run_git(["commit", "-m", split_message])
                    new_commits.append(split_message)

        print(f"Successfully created {len(new_commits)} commits:")
        for i, message in enumerate(new_commits, 1):
            first_line = message.split("\n")[0]
            print(f"  {i}. {first_line}")

        return True

    def split_commits(self, base_ref: Optional[str] = None, no_prompt: bool = False) -> None:
        """Split commits into separate commits, one per file."""
        try:
            # Create backup
            self.create_backup()

            # Get commits to split
            commits = self.get_commits_to_rebase(base_ref)
            if not commits:
                print("No commits found to split")
                self.cleanup_backup()
                return

            print(f"Found {len(commits)} commits to split")

            # Perform split rebase
            success = self.perform_split_rebase(commits, no_prompt=no_prompt)

            if success:
                self.cleanup_backup()
            else:
                self.restore_from_backup()

        except Exception as e:
            print(f"Error: {e}")
            self.restore_from_backup()
            sys.exit(1)

    def configure_repo(self, options: dict[str, Any]) -> None:
        """Configure repository/global git settings to reduce merge pain.

        Currently implements the 'safe' preset:
        - Enable rerere with autoUpdate
        - Use zdiff3 conflict style for clearer conflicts
        - Use patience diff with indent heuristic
        - Enable rename detection and raise rename limits
        - Use merge backend for rebase and autostash
        - Improve diff coloring for moved lines

        Options:
            scope: 'local' or 'global' (default: 'local')
            preset: 'safe'|'opinionated'|'custom' (currently only 'safe' applied)
            dry_run: bool (default: False)
        """
        scope = options.get("scope", "local")
        # preset currently unused; only 'safe' implemented
        dry_run = bool(options.get("dry_run", False))

        if scope not in {"local", "global"}:
            scope = "local"

        # Only implement 'safe' preset for now; other presets are ignored gracefully
        settings: list[tuple[str, str]] = [
            ("rerere.enabled", "true"),
            ("rerere.autoUpdate", "true"),
            ("merge.conflictStyle", "zdiff3"),
            ("diff.algorithm", "patience"),
            ("diff.indentHeuristic", "true"),
            ("diff.renames", "true"),
            ("merge.renames", "true"),
            ("merge.renameLimit", "32767"),
            ("rebase.backend", "merge"),
            ("rebase.autoStash", "true"),
            ("diff.colorMoved", "zebra"),
            ("color.ui", "auto"),
        ]

        scope_flag = "--global" if scope == "global" else "--local"

        if dry_run:
            print("Planned git configuration changes:")
            for key, value in settings:
                print(f"  git config {scope_flag} {key} {value}")
            return

        for key, value in settings:
            self.run_git(["config", scope_flag, key, value])

    def rebase_skip_merged(self, options: dict[str, Any]) -> None:
        """Rebase a branch onto base while skipping commits already on base by content.

        Uses `git cherry -v <base> <branch>` to determine which commits are unique (+ lines)
        and replays only those commits in order onto the base. Safe and explicit alternative
        to a regular rebase when ancestor SHAs changed but content landed unchanged.
        """
        base_ref = options.get("base") or "origin/main"
        branch = (
            options.get("branch")
            or self.run_git(["branch", "--show-current"]).stdout.strip()
        )
        dry_run = bool(options.get("dry_run", False))
        prompt = bool(options.get("prompt", True))
        backup = bool(options.get("backup", True))
        conflict_bias = options.get("conflict_bias", "none")
        chunk_size = options.get("chunk_size")
        by_groups = bool(options.get("by_groups", False))
        max_conflicts = options.get("max_conflicts")
        optimize_merge = bool(options.get("optimize_merge", False))
        rerere_cache = options.get("rerere_cache")
        use_rerere_cache = bool(options.get("use_rerere_cache", False))
        auto_resolve_trivial = bool(options.get("auto_resolve_trivial", False))
        rename_detect = True if options.get("rename_detect", True) else False

        # Validations
        if chunk_size is not None and chunk_size <= 0:
            print("Invalid --chunk-size: must be > 0")
            return
        if max_conflicts is not None and max_conflicts <= 0:
            print("Invalid --max-conflicts: must be > 0")
            return
        if use_rerere_cache and not rerere_cache:
            print("--use-rerere-cache requires --rerere-cache PATH")
            return
        if by_groups:
            print("Warning: --by-groups not yet supported; proceeding without grouping")

        # Build temporary config prefix if requested
        git_prefix: list[str] = []
        if optimize_merge:
            git_prefix = [
                "-c",
                "rerere.enabled=true",
                "-c",
                "rerere.autoUpdate=true",
                "-c",
                "merge.conflictStyle=zdiff3",
                "-c",
                "diff.algorithm=patience",
                "-c",
                "diff.indentHeuristic=true",
                "-c",
                "diff.renames=true",
                "-c",
                "merge.renames=true",
                "-c",
                "merge.renameLimit=32767",
                "-c",
                "rebase.backend=merge",
                "-c",
                "rebase.autoStash=true",
            ]

        # Ensure refs are up to date (best-effort)
        self.run_git(git_prefix + ["fetch", "--all", "--prune"], check_output=False)

        # Compute branch unique commits vs base via git cherry
        cherry = self.run_git(git_prefix + ["cherry", "-v", base_ref, branch])
        unique_lines = [
            line for line in cherry.stdout.strip().split("\n") if line.startswith("+")
        ]

        unique_commits = []
        for line in unique_lines:
            # format: "+ <sha> <subject>"
            parts = line.split(" ", 2)
            if len(parts) >= 2:
                unique_commits.append(parts[1])

        print(
            f"Found {len(unique_commits)} commits unique to {branch} relative to {base_ref}"
        )

        if dry_run:
            if unique_commits:
                print("Would replay (oldest to newest):")
                for sha in unique_commits:
                    print(f"  {sha[:8]}")
            else:
                print(
                    "No commits to replay; branch is effectively up-to-date with base"
                )
            return

        # Nothing to do
        if not unique_commits:
            print("No commits to replay; branch is effectively up-to-date with base")
            return

        if prompt:
            resp = input(
                f"Proceed to rebase {branch} onto {base_ref} replaying {len(unique_commits)} commits? (y/N): "
            )
            if resp.lower() != "y":
                print("Operation cancelled")
                return

        # Create safety backup
        backup_branch = None
        if backup:
            backup_branch = f"backup-{branch}-rebase-skip-{self.run_git(git_prefix + ['rev-parse', 'HEAD']).stdout.strip()[:8]}"
            self.run_git(git_prefix + ["branch", backup_branch, branch])
            print(f"Created backup branch: {backup_branch}")

        # Optionally import rerere cache
        imported_rerere = False
        rr_cache_dir = os.path.join(".git", "rr-cache")
        if use_rerere_cache and rerere_cache:
            try:
                if os.path.isdir(rerere_cache):
                    os.makedirs(rr_cache_dir, exist_ok=True)
                    for root, _dirs, files in os.walk(rerere_cache):
                        rel = os.path.relpath(root, rerere_cache)
                        target_root = (
                            os.path.join(rr_cache_dir, rel)
                            if rel != "."
                            else rr_cache_dir
                        )
                        os.makedirs(target_root, exist_ok=True)
                        for fname in files:
                            src = os.path.join(root, fname)
                            dst = os.path.join(target_root, fname)
                            try:
                                shutil.copy2(src, dst)
                            except Exception:
                                pass
                    imported_rerere = True
            except Exception:
                print("Warning: failed to import rerere cache; continuing")

        # Create a temp branch from base and replay unique commits
        temp_branch = f"{branch}-rebased"
        # Start from base
        self.run_git(git_prefix + ["switch", "-c", temp_branch, base_ref])
        conflicts_count = 0
        merge_opts: list[str] = []
        if conflict_bias in {"ours", "theirs"}:
            merge_opts += ["-X", conflict_bias]
        if not rename_detect:
            merge_opts += ["-X", "no-renames"]
        else:
            merge_opts += ["-X", "find-renames"]
        if auto_resolve_trivial:
            merge_opts += ["-X", "ignore-space-change"]

        def replay_range(commits: list[str]) -> bool:
            nonlocal conflicts_count
            for sha in commits:
                result = self.run_git(
                    git_prefix + ["cherry-pick", *merge_opts, sha], check_output=False
                )
                if result.returncode != 0:
                    # Try trivial auto-continue if requested
                    if auto_resolve_trivial:
                        diff = self.run_git(
                            ["diff", "--name-only", "--diff-filter=U"],
                            check_output=False,
                        )
                        if diff.returncode == 0 and not diff.stdout.strip():
                            cont = self.run_git(
                                ["cherry-pick", "--continue"], check_output=False
                            )
                            if cont.returncode == 0:
                                continue
                    conflicts_count += 1
                    print(f"Cherry-pick failed for {sha[:8]}: {result.stderr}")
                    if max_conflicts is not None and conflicts_count >= max_conflicts:
                        print("Max conflicts reached; aborting")
                        return False
                    # Abort this pick and stop
                    self.run_git(["cherry-pick", "--abort"], check_output=False)
                    return False
            return True

        if chunk_size and chunk_size > 0:
            for i in range(0, len(unique_commits), chunk_size):
                chunk = unique_commits[i : i + chunk_size]
                ok = replay_range(chunk)
                if not ok:
                    # Restore original branch
                    self.run_git(["switch", branch], check_output=False)
                    self.run_git(["branch", "-D", temp_branch], check_output=False)
                    if backup_branch:
                        print(f"You can recover previous state from {backup_branch}")
                    return
        else:
            ok = replay_range(unique_commits)
            if not ok:
                self.run_git(["switch", branch], check_output=False)
                self.run_git(["branch", "-D", temp_branch], check_output=False)
                if backup_branch:
                    print(f"You can recover previous state from {backup_branch}")
                return

        # Fast-forward branch to the temp branch state
        self.run_git(git_prefix + ["branch", "-f", branch, temp_branch])
        self.run_git(git_prefix + ["switch", branch])
        self.run_git(git_prefix + ["branch", "-D", temp_branch], check_output=False)

        # Optionally export rerere cache
        if use_rerere_cache and rerere_cache and imported_rerere:
            try:
                os.makedirs(rerere_cache, exist_ok=True)
                for root, _dirs, files in os.walk(rr_cache_dir):
                    rel = os.path.relpath(root, rr_cache_dir)
                    target_root = (
                        os.path.join(rerere_cache, rel) if rel != "." else rerere_cache
                    )
                    os.makedirs(target_root, exist_ok=True)
                    for fname in files:
                        src = os.path.join(root, fname)
                        dst = os.path.join(target_root, fname)
                        try:
                            shutil.copy2(src, dst)
                        except Exception:
                            pass
            except Exception:
                print("Warning: failed to export rerere cache")
        print("Rebase-skip-merged completed successfully.")

    # Helper commands for smart orchestration
    def preflight_check(self, options: dict[str, Any]) -> None:
        base = options.get("base") or "origin/main"
        branch = (
            options.get("branch")
            or self.run_git(["branch", "--show-current"]).stdout.strip()
        )
        allow_dirty = bool(options.get("allow_dirty", False))
        allow_wip = bool(options.get("allow_wip", False))
        dry_run = bool(options.get("dry_run", False))

        # Fetch
        self.run_git(["fetch", "--all", "--prune"], check_output=False)

        # Worktree clean
        status = self.run_git(["status", "--porcelain=v1"]).stdout
        if status.strip() and not allow_dirty:
            print("Working tree is dirty; commit or stash changes or use --allow-dirty")
            return

        # Check WIP in head commit message if requested
        head_msg = self.run_git(["show", "-s", "--pretty=%s"]).stdout.strip()
        if not allow_wip and ("WIP" in head_msg or head_msg.lower().startswith("wip")):
            print("Head commit looks like WIP; use --allow-wip to proceed")
            return

        # Show behind/ahead relative to base
        ahead = self.run_git(
            ["rev-list", "--left-right", "--count", f"{base}...{branch}"]
        ).stdout.strip()
        print(f"Preflight OK. Behind/ahead (base...branch): {ahead}")
        if dry_run:
            print("Dry-run: no changes made")

    def select_base(self, options: dict[str, Any]) -> str:
        preferred: list[str] = options.get("preferred") or [
            "origin/main",
            "main",
            "origin/master",
            "master",
        ]
        fallback: str = options.get("fallback") or "HEAD~10"
        for cand in preferred:
            try:
                mb = self.run_git(["merge-base", "HEAD", cand]).stdout.strip()
                if mb:
                    return cand
            except GitError:
                continue
        return fallback

    def auto_continue(self) -> None:
        # Attempt to continue an in-progress rebase/cherry-pick
        # First try cherry-pick
        res = self.run_git(["cherry-pick", "--continue"], check_output=False)
        if res.returncode == 0:
            print("Continued cherry-pick")
            return
        # Then try rebase
        res = self.run_git(["rebase", "--continue"], check_output=False)
        if res.returncode == 0:
            print("Continued rebase")
            return
        print("Nothing to continue")

    def auto_resolve_trivial(self) -> None:
        # Attempt to resolve trivial conflicts by ignoring whitespace and continuing
        diff = self.run_git(
            ["diff", "--name-only", "--diff-filter=U"], check_output=False
        )
        if diff.returncode != 0:
            print("No conflict information available")
            return
        # Try a continue; if it fails, abort the attempt
        cont = self.run_git(["cherry-pick", "--continue"], check_output=False)
        if cont.returncode == 0:
            print("Continued after trivial resolution (cherry-pick)")
            return
        cont = self.run_git(["rebase", "--continue"], check_output=False)
        if cont.returncode == 0:
            print("Continued after trivial resolution (rebase)")
            return
        print("Trivial auto-resolution not applicable")

    def chunked_replay(self, options: dict[str, Any]) -> None:
        base = options.get("base")
        commits: list[str] = options.get("commits") or []
        chunk_size: int = int(options.get("chunk_size") or 0)
        if not base or not commits or chunk_size <= 0:
            print("Missing required arguments for chunked-replay")
            return
        temp = (
            f"chunked-{self.run_git(['rev-parse', '--short', 'HEAD']).stdout.strip()}"
        )
        self.run_git(["switch", "-c", temp, base])
        for i in range(0, len(commits), chunk_size):
            chunk = commits[i : i + chunk_size]
            result = self.run_git(["cherry-pick", *chunk], check_output=False)
            if result.returncode != 0:
                print("Chunk failed; aborting and leaving temp branch for inspection")
                self.run_git(["cherry-pick", "--abort"], check_output=False)
                return
        print("Chunked replay completed")

    def range_diff_report(self, old: str, new: str) -> None:
        res = self.run_git(["range-diff", old, new], check_output=False)
        if res.returncode == 0:
            print(res.stdout)
        else:
            print(res.stderr)

    def validate(self, options: dict[str, Any]) -> None:
        do_lint = bool(options.get("lint", False))
        do_test = bool(options.get("test", False))
        do_build = bool(options.get("build", False))
        if not any([do_lint, do_test, do_build]):
            print("Nothing to validate")
            return
        if do_lint:
            self.run_git(["rev-parse", "HEAD"], check_output=False)
            print("Lint placeholder; hook your linter here")
        if do_test:
            print("Test placeholder; hook your test runner here")
        if do_build:
            print("Build placeholder; hook your build here")

    def rerere_share(self, options: dict[str, Any]) -> None:
        action = options.get("action")
        path = options.get("path")
        if not action or not path:
            print("Missing action or path")
            return
        rr_cache_dir = os.path.join(".git", "rr-cache")
        if action == "import":
            if not os.path.isdir(path):
                print("Invalid rerere cache path")
                return
            os.makedirs(rr_cache_dir, exist_ok=True)
            for root, _dirs, files in os.walk(path):
                rel = os.path.relpath(root, path)
                target_root = (
                    os.path.join(rr_cache_dir, rel) if rel != "." else rr_cache_dir
                )
                os.makedirs(target_root, exist_ok=True)
                for fname in files:
                    src = os.path.join(root, fname)
                    dst = os.path.join(target_root, fname)
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
            print("Imported rerere cache")
        elif action == "export":
            os.makedirs(path, exist_ok=True)
            if not os.path.isdir(rr_cache_dir):
                print("No local rerere cache to export")
                return
            for root, _dirs, files in os.walk(rr_cache_dir):
                rel = os.path.relpath(root, rr_cache_dir)
                target_root = os.path.join(path, rel) if rel != "." else path
                os.makedirs(target_root, exist_ok=True)
                for fname in files:
                    src = os.path.join(root, fname)
                    dst = os.path.join(target_root, fname)
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
            print("Exported rerere cache")

    def smart_rebase(self, options: dict[str, Any]) -> None:
        """Orchestrated rebase flow combining preflight, dedup-aware replay, and validation."""
        branch = (
            options.get("branch")
            or self.run_git(["branch", "--show-current"]).stdout.strip()
        )
        base = options.get("base") or self.select_base({})
        dry_run = bool(options.get("dry_run", False))
        prompt = bool(options.get("prompt", True))
        backup = bool(options.get("backup", True))
        optimize_merge = bool(options.get("optimize_merge", False))
        conflict_bias = options.get("conflict_bias", "none")
        chunk_size = options.get("chunk_size")
        auto_resolve_trivial = bool(options.get("auto_resolve_trivial", False))
        max_conflicts = options.get("max_conflicts")
        rename_detect = True if options.get("rename_detect", True) else False
        do_lint = bool(options.get("lint", False))
        do_test = bool(options.get("test", False))
        do_build = bool(options.get("build", False))
        # 'report' reserved for future detailed reporting formats
        summary = bool(options.get("summary", True))
        skip_merged = bool(options.get("skip_merged", True))

        # Preflight
        self.preflight_check(
            {
                "base": base,
                "branch": branch,
                "allow_dirty": False,
                "allow_wip": False,
                "dry_run": dry_run,
            }
        )
        if dry_run:
            print(f"Would rebase {branch} onto {base} (smart mode)")
            return

        # Backup
        if backup:
            self.create_backup()

        # Rebase
        try:
            if skip_merged:
                self.rebase_skip_merged(
                    {
                        "base": base,
                        "branch": branch,
                        "prompt": prompt,
                        "backup": False,  # we already backed up
                        "dry_run": False,
                        "optimize_merge": optimize_merge,
                        "conflict_bias": conflict_bias,
                        "chunk_size": chunk_size,
                        "auto_resolve_trivial": auto_resolve_trivial,
                        "max_conflicts": max_conflicts,
                        "rename_detect": rename_detect,
                    }
                )
            else:
                # fallback to a plain rebase with optional conflict bias
                args = ["rebase", base]
                if conflict_bias in {"ours", "theirs"}:
                    args = ["rebase", "-X", conflict_bias, base]
                result = self.run_git(args, check_output=False)
                if result.returncode != 0:
                    print(f"Rebase failed: {result.stderr}")
                    raise GitError("rebase failed")

            # Validation
            if any([do_lint, do_test, do_build]):
                self.validate({"lint": do_lint, "test": do_test, "build": do_build})

            if summary:
                # Print a brief range-diff summary for visibility
                base_range = f"{base}...{branch}"
                head_range = f"{base}...{branch}"
                self.range_diff_report(base_range, head_range)

            if backup:
                self.cleanup_backup()
        except Exception as e:
            print(f"Error during smart-rebase: {e}")
            if backup:
                self.restore_from_backup()
            raise

    def smart_merge(self, options: dict[str, Any]) -> None:
        """Preview or perform a merge with ort + rename detection and safety.

        Preview uses `git merge --no-commit --no-ff` and aborts to avoid state changes.
        Apply performs the merge and commits if clean, or stops on conflicts.
        """
        source = options.get("branch")
        target = (
            options.get("into")
            or self.run_git(["branch", "--show-current"]).stdout.strip()
        )
        if not source:
            print("Missing --branch for smart-merge")
            return

        apply = bool(options.get("apply", False))
        prompt = bool(options.get("prompt", True))
        backup = bool(options.get("backup", True))
        optimize_merge = bool(options.get("optimize_merge", False))
        conflict_bias = options.get("conflict_bias", "none")
        rename_detect = True if options.get("rename_detect", True) else False
        rename_threshold = options.get("rename_threshold")
        auto_resolve_trivial = bool(options.get("auto_resolve_trivial", False))
        max_conflicts = options.get("max_conflicts")
        do_lint = bool(options.get("lint", False))
        do_test = bool(options.get("test", False))
        do_build = bool(options.get("build", False))

        # Build -c prefix for temporary safer settings
        git_prefix: list[str] = []
        if optimize_merge:
            git_prefix = [
                "-c",
                "rerere.enabled=true",
                "-c",
                "merge.conflictStyle=zdiff3",
                "-c",
                "diff.algorithm=patience",
                "-c",
                "diff.indentHeuristic=true",
                "-c",
                "diff.renames=true",
                "-c",
                "merge.renames=true",
                "-c",
                "merge.renameLimit=32767",
            ]

        # Ensure target checked out
        self.run_git(["switch", target])

        # Build merge args
        merge_args = ["merge", "--no-ff", source]
        if not apply:
            merge_args = ["merge", "--no-commit", "--no-ff", source]
        if conflict_bias in {"ours", "theirs"}:
            merge_args[1:1] = ["-X", conflict_bias]
        if rename_detect:
            merge_args[1:1] = ["-X", "find-renames"]
            if isinstance(rename_threshold, int):
                merge_args[1:1] = ["-X", f"find-renames={rename_threshold}"]
        else:
            merge_args[1:1] = ["-X", "no-renames"]

        if not apply:
            print(f"Previewing merge of {source} into {target}...")
        else:
            if prompt:
                resp = input(f"Proceed to merge {source} into {target}? (y/N): ")
                if resp.lower() != "y":
                    print("Merge cancelled")
                    return
            if backup:
                self.create_backup()

        result = self.run_git(git_prefix + merge_args, check_output=False)
        if result.returncode == 0:
            if not apply:
                print("Merge would be clean")
                # Abort preview merge to restore state
                self.run_git(["merge", "--abort"], check_output=False)
            else:
                print("Merge completed cleanly")
                if do_lint or do_test or do_build:
                    self.validate({"lint": do_lint, "test": do_test, "build": do_build})
                if backup:
                    self.cleanup_backup()
            return

        # Handle conflicts
        print(f"Merge resulted in conflicts: {result.stderr}")
        if auto_resolve_trivial:
            # Try to continue if only whitespace/superficial
            cont = self.run_git(["commit", "--no-edit"], check_output=False)
            if cont.returncode == 0:
                print("Merge committed after trivial resolution")
                if backup:
                    self.cleanup_backup()
                return

        if not apply:
            # Abort preview merge
            self.run_git(["merge", "--abort"], check_output=False)
        else:
            # Leave repository in conflict state for manual resolution
            if backup and max_conflicts:
                # Just informational; we don't count individual conflicts here
                print(
                    "Conflicts present; resolve manually or abort and restore from backup"
                )
        print("Merge preview/operation ended with conflicts surfaced.")

    def smart_revert(self, options: dict[str, Any]) -> None:
        """Preview or perform revert(s) with strategy hints and safety."""
        commits: list[str] = options.get("commits") or []
        range_expr: Optional[str] = options.get("range")
        count: Optional[int] = options.get("count")

        apply = bool(options.get("apply", False))
        prompt = bool(options.get("prompt", True))
        backup = bool(options.get("backup", True))
        optimize_merge = bool(options.get("optimize_merge", False))
        conflict_bias = options.get("conflict_bias", "none")
        rename_detect = True if options.get("rename_detect", True) else False
        rename_threshold = options.get("rename_threshold")
        # auto_resolve_trivial currently not used in revert flow
        max_conflicts = options.get("max_conflicts")
        do_lint = bool(options.get("lint", False))
        do_test = bool(options.get("test", False))
        do_build = bool(options.get("build", False))

        # Resolve commit list if not explicitly provided
        if not commits:
            commits = self.select_reverts({"range": range_expr, "count": count})
        if not commits:
            print("No commits selected to revert")
            return

        # Temporary safer settings
        git_prefix: list[str] = []
        if optimize_merge:
            git_prefix = [
                "-c",
                "rerere.enabled=true",
                "-c",
                "merge.conflictStyle=zdiff3",
                "-c",
                "diff.algorithm=patience",
                "-c",
                "diff.indentHeuristic=true",
                "-c",
                "diff.renames=true",
                "-c",
                "merge.renames=true",
                "-c",
                "merge.renameLimit=32767",
            ]

        # Build revert options
        revert_opts: list[str] = ["revert"]
        if not apply:
            revert_opts.append("--no-commit")
        if conflict_bias in {"ours", "theirs"}:
            revert_opts += ["-X", conflict_bias]
        if rename_detect:
            revert_opts += ["-X", "find-renames"]
            if isinstance(rename_threshold, int):
                revert_opts += ["-X", f"find-renames={rename_threshold}"]
        else:
            revert_opts += ["-X", "no-renames"]

        # Confirm apply
        if apply and prompt:
            resp = input(f"Proceed to revert {len(commits)} commit(s)? (y/N): ")
            if resp.lower() != "y":
                print("Revert cancelled")
                return
        if apply and backup:
            self.create_backup()

        # Preview/apply sequentially
        conflicts = 0
        for sha in commits:
            result = self.run_git(git_prefix + revert_opts + [sha], check_output=False)
            if result.returncode != 0:
                print(f"Revert failed for {sha[:8]}: {result.stderr}")
                conflicts += 1
                if not apply:
                    # Abort preview revert and stop
                    self.run_git(["revert", "--abort"], check_output=False)
                    break
                if max_conflicts is not None and conflicts >= max_conflicts:
                    print("Max conflicts reached; stopping further reverts")
                    break
                # For apply mode, leave conflict state for manual resolution
                break

        if not apply:
            if conflicts == 0:
                print("Revert would be clean")
            else:
                print("Revert preview ended with conflicts surfaced.")
            return

        # Apply mode: commit if clean
        if conflicts == 0:
            commit_res = self.run_git(["commit", "--no-edit"], check_output=False)
            if commit_res.returncode == 0:
                print("Revert committed successfully")
                if do_lint or do_test or do_build:
                    self.validate({"lint": do_lint, "test": do_test, "build": do_build})
                if backup:
                    self.cleanup_backup()
                return

        print("Revert ended with conflicts; resolve manually or abort and restore.")

    def select_reverts(self, options: dict[str, Any]) -> list[str]:
        """Helper to select commits to revert using filters."""
        range_expr: Optional[str] = options.get("range")
        count: Optional[int] = options.get("count")
        grep: Optional[str] = options.get("grep")
        author: Optional[str] = options.get("author")

        args = ["log", "--pretty=%H"]
        if count:
            args += [f"-n{count}"]
        if grep:
            args += [f"--grep={grep}"]
        if author:
            args += [f"--author={author}"]
        if range_expr:
            args += [range_expr]
        shas = self.run_git(args).stdout.strip().splitlines()
        # Default to empty list if no output
        return [s for s in shas if s]

    def run(
        self, base_ref: Optional[str] = None, similarity_threshold: float = 0.3, no_prompt: bool = False
    ) -> None:
        """Main execution function."""
        try:
            # Create backup
            self.create_backup()

            # Get commits to rebase
            commits = self.get_commits_to_rebase(base_ref)
            if not commits:
                print("No commits found to rebase")
                self.cleanup_backup()
                return

            print(f"Found {len(commits)} commits to analyze")

            # Group commits
            groups = self.group_commits(commits, similarity_threshold)

            # Perform rebase
            success = self.perform_rebase(groups, no_prompt=no_prompt)

            if success:
                self.cleanup_backup()
            else:
                self.restore_from_backup()

        except Exception as e:
            print(f"Error: {e}")
            self.restore_from_backup()
            sys.exit(1)


class GitError(Exception):
    """Custom exception for git-related errors."""

    pass
