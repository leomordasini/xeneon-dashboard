import subprocess
import sys
import os

# Named tunnel — URL is always https://xeneon.mordasini.com
# Run: cloudflared.exe tunnel run --config cloudflared-config.yml xeneon

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cloudflared = os.path.join(script_dir, "cloudflared.exe")
    config = os.path.join(script_dir, "cloudflared-config.yml")

    if not os.path.exists(cloudflared):
        print("ERROR: cloudflared.exe not found in", script_dir)
        sys.exit(1)

    if not os.path.exists(config):
        print("ERROR: cloudflared-config.yml not found. See README for setup.")
        sys.exit(1)

    print("Starting named tunnel → https://xeneon.mordasin.com")
    subprocess.run([cloudflared, "tunnel", "--config", config, "run", "xeneon"])

if __name__ == "__main__":
    main()
