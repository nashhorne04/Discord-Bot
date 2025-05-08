import subprocess
import os
import sys
import time

# Get root directory (where this script is located)
root_dir = os.path.dirname(os.path.abspath(__file__))

print(f"Root directory: {root_dir}")

# List of bot folders
bot_folders = ["lux", "dominus", "vox","seraph","vitalis","stratos"]

processes = []

# Launch each bot
for folder in bot_folders:
    bot_path = os.path.join(root_dir, folder)
    main_script = os.path.join(bot_path, "main.py")

    # Check if the main.py exists
    if not os.path.isfile(main_script):
        print(f"❌ Error: {main_script} does not exist!")
        continue

    print(f"🚀 Launching bot from: {bot_path}")

    # Use sys.executable to use the same Python that ran this script
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=bot_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    processes.append((folder, proc))

# Wait a moment to see if any fail immediately
time.sleep(2)

# Check status of all launched processes
for folder, proc in processes:
    if proc.poll() is not None:
        # Process exited early
        stdout, stderr = proc.communicate()
        print(f"\n⚠️ Bot '{folder}' exited with code {proc.returncode}")
        print("STDOUT:")
        print(stdout)
        print("STDERR:")
        print(stderr)
    else:
        print(f"✅ Bot '{folder}' is running (PID: {proc.pid})")

# Keep the launcher alive so you can see output or handle Ctrl+C
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Shutting down all bots...")
    for _, proc in processes:
        proc.terminate()
    for _, proc in processes:
        proc.wait()
    print("All bots terminated.")