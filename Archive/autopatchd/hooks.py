"""
Hook system for pre/post patching scripts
"""

import subprocess
import logging
import os
from pathlib import Path


class HookRunner:
    """Manages and runs pre/post patching hooks"""
    
    HOOKS_DIR = Path("/etc/autopatchd/hooks")
    
    def __init__(self):
        self.pre_hooks_dir = self.HOOKS_DIR / "pre.d"
        self.post_hooks_dir = self.HOOKS_DIR / "post.d"
        
        # Ensure hook directories exist
        self.pre_hooks_dir.mkdir(parents=True, exist_ok=True)
        self.post_hooks_dir.mkdir(parents=True, exist_ok=True)
    
    def run_pre_hooks(self):
        """Run all pre-patching hooks"""
        self._run_hooks(self.pre_hooks_dir, "pre")
    
    def run_post_hooks(self):
        """Run all post-patching hooks"""
        self._run_hooks(self.post_hooks_dir, "post")
    
    def _run_hooks(self, hooks_dir: Path, hook_type: str):
        """Run all executable scripts in a hook directory"""
        if not hooks_dir.exists():
            return
        
        # Get all executable files, sorted by name
        hooks = [f for f in hooks_dir.iterdir() 
                if f.is_file() and os.access(f, os.X_OK)]
        hooks.sort()
        
        if not hooks:
            logging.info(f"No {hook_type}-hooks found")
            return
        
        logging.info(f"Running {len(hooks)} {hook_type}-hooks")
        
        for hook in hooks:
            try:
                logging.info(f"Running {hook_type}-hook: {hook.name}")
                
                result = subprocess.run(
                    [str(hook)],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    env=dict(os.environ, AUTOPATCHD_HOOK_TYPE=hook_type)
                )
                
                if result.returncode == 0:
                    logging.info(f"{hook_type}-hook {hook.name} completed successfully")
                    if result.stdout:
                        logging.debug(f"{hook.name} stdout: {result.stdout}")
                else:
                    logging.warning(f"{hook_type}-hook {hook.name} failed with exit code {result.returncode}")
                    if result.stderr:
                        logging.warning(f"{hook.name} stderr: {result.stderr}")
                
            except subprocess.TimeoutExpired:
                logging.error(f"{hook_type}-hook {hook.name} timed out")
            except Exception as e:
                logging.error(f"Failed to run {hook_type}-hook {hook.name}: {e}")


def create_example_hooks():
    """Create example hook scripts"""
    hooks_dir = Path("/etc/autopatchd/hooks")
    
    # Create pre-hook example
    pre_example = hooks_dir / "pre.d" / "00-example.sh.disabled"
    pre_example.parent.mkdir(parents=True, exist_ok=True)
    
    with open(pre_example, 'w') as f:
        f.write("""#!/bin/bash
# Example pre-patching hook
# Rename to remove .disabled to activate

echo "Running pre-patch hook"

# Example: Stop a service before patching
# systemctl stop myapp

# Example: Create a backup
# tar -czf /backup/pre-patch-$(date +%Y%m%d).tar.gz /etc

exit 0
""")
    
    # Create post-hook example
    post_example = hooks_dir / "post.d" / "99-example.sh.disabled"
    post_example.parent.mkdir(parents=True, exist_ok=True)
    
    with open(post_example, 'w') as f:
        f.write("""#!/bin/bash
# Example post-patching hook
# Rename to remove .disabled to activate

echo "Running post-patch hook"

# Example: Start a service after patching
# systemctl start myapp

# Example: Send notification
# curl -X POST -H 'Content-type: application/json' --data '{"text":"Patching completed on $(hostname)"}' YOUR_SLACK_WEBHOOK_URL

exit 0
""")
    
    # Make them readable but not executable (since they're examples)
    pre_example.chmod(0o644)
    post_example.chmod(0o644)