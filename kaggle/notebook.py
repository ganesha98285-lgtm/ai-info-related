# =====================================================================
# Jon & Katie — FULL daily pipeline on Kaggle's FREE GPU (real LTX-Video)
# ---------------------------------------------------------------------
# Paste this into a Kaggle Notebook cell. In the notebook settings:
#   - Accelerator: GPU T4 x2 (or P100)
#   - Internet: ON
#   - Add Secrets (Add-ons -> Secrets): GEMINI_API_KEY, YOUTUBE_TOKEN_JSON
# Then Run All. You can also SCHEDULE the notebook to run daily.
#
# This generates REAL motion video (LTX-Video image-to-video) from the
# character sheet, assembles shorts, and uploads them to YouTube.
# =====================================================================

# --- 1) system + python deps -----------------------------------------
import subprocess, sys, os

subprocess.run("apt-get -qq update && apt-get -qq install -y ffmpeg", shell=True)
subprocess.run(
    sys.executable + " -m pip install -q "
    "'diffusers>=0.35.1' 'transformers>=4.44' accelerate imageio-ffmpeg "
    "sentencepiece edge-tts google-generativeai google-api-python-client "
    "google-auth-oauthlib google-auth-httplib2 pytz Pillow python-dotenv requests",
    shell=True,
)

# --- 2) get the repo --------------------------------------------------
REPO = "https://github.com/ganesha98285-lgtm/jab-ketty-met-john"
if not os.path.exists("/kaggle/working/jab-ketty-met-john"):
    subprocess.run(f"git clone {REPO} /kaggle/working/jab-ketty-met-john", shell=True)
os.chdir("/kaggle/working/jab-ketty-met-john")
subprocess.run("git pull", shell=True)

# --- 3) secrets (from Kaggle Add-ons -> Secrets) ----------------------
from kaggle_secrets import UserSecretsClient  # type: ignore

sec = UserSecretsClient()
os.environ["GEMINI_API_KEY"] = sec.get_secret("GEMINI_API_KEY")

os.makedirs("secrets", exist_ok=True)
with open("secrets/youtube_token.json", "w") as f:
    f.write(sec.get_secret("YOUTUBE_TOKEN_JSON"))

# --- 4) pipeline config ----------------------------------------------
os.environ["VIDEO_BACKEND"] = "ltx"          # REAL image-to-video motion
os.environ["SHORTS_ONLY"] = "true"
os.environ["SHORTS_PER_DAY"] = "1"           # start with 1 to confirm; raise to 6 later
os.environ["UPLOAD_TARGETS"] = "youtube"
os.environ["YOUTUBE_PRIVACY"] = "public"     # or "unlisted" to review first
os.environ["SCHEDULE_TO_PEAK"] = "false"     # true => schedule to prime-time slots
os.environ["USA_TIMEZONE"] = "America/New_York"
os.environ["INDIA_TIMEZONE"] = "Asia/Kolkata"

# --- 5) run the whole daily flow -------------------------------------
subprocess.run(sys.executable + " -m src.pipeline --once", shell=True, check=False)

print("Done. Check output/<date>/ for the video + shorts, and your YouTube channel.")
