# Deploying the backend and building the release APK

The backend is a Docker container (`backend/Dockerfile`) that needs **PostgreSQL**, a **persistent volume** for
uploaded plans, and a few environment variables. `render.yaml` describes all of that for Render; Railway and
Fly.io work with the same Dockerfile and variables.

## 0. What is protected, and what is not

* The backend has **no user accounts**. A **shared API key** gates every route except `/api/health`
  (`X-API-Key` header). It stops strangers creating projects, uploading files and spending your AI credit.
* The key is compiled into the APK, so **anyone who unpacks the APK can read it**. Hand the APK only to people
  who should have access, and rotate the key (redeploy the backend + rebuild the APK) if it leaks.
* With a real AI provider in production the backend **refuses to start without `API_KEY`**.
* Plans are stored on the volume and in Postgres: back them up if they matter.

## 1. Make the API key

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Keep it in a password manager. Do not commit it, paste it into chats or put it in a file in the repository.

## 2. Deploy on Render

1. Push the branch you want to run (the blueprint uses `remediation/phase1-geometry`; change `branch:` in
   `render.yaml` to `main` once merged).
2. Render dashboard → **New → Blueprint** → select this repository → it reads `render.yaml`.
3. Check the plans/prices it shows (⚠ plan names in `render.yaml` are unverified). A disk and a non-expiring
   database need paid plans. On the free tier uploaded plans vanish on every restart and the database expires.
4. When prompted, enter **`API_KEY`** (from step 1). Leave `GEMINI_API_KEY` / `OPENAI_API_KEY` empty for now.
5. Wait for the deploy, then open `https://<service>.onrender.com/api/health`. Expected:
   `{"status":"ok", ... "environment":"production", "ai_provider":"mock" ...}`.

`AI_PROVIDER=mock` returns the same demo rooms for every upload. To read real plans set
`AI_PROVIDER=gemini` (or `openai`) **and** the matching key in the service's environment, then redeploy.

### Other hosts

Same image, same variables: `DATABASE_URL` (Postgres), `API_KEY`, `APP_ENV=production`, `DEBUG=False`,
`AI_PROVIDER`, optional provider keys, and a volume mounted at `/app/uploads`. The container listens on `$PORT`
(default 8000) and exposes `/api/health` for health checks. Put it behind HTTPS (hosts do this for you).

### Verify protection from outside

```powershell
curl https://<host>/api/projects                                  # -> 401 Invalid or missing API key.
curl -H "X-API-Key: <key>" https://<host>/api/projects            # -> []
```

## 3. Build the APK

```powershell
$env:VOLTPLAN_API_URL = "https://<host>/api"
$env:VOLTPLAN_API_KEY = "<the same API_KEY>"
.\scripts\build_release_apk.ps1
```

The script refuses plain `http://` (Android blocks it and the key would travel unencrypted), checks that the
backend is healthy and accepts the key, warns if the backend runs the mock AI provider, builds, and prints the
APK path, size and SHA-256. Output: `build\app\outputs\flutter-apk\app-release.apk`.

Install on a phone: copy the APK across (or `adb install -r app-release.apk`) and allow installing from that source.

### Signing

Without `android/key.properties` the release build is signed with the **debug key**: fine for sideloading and
testing, **not accepted by the Play Store**, and updates must keep using the same key. For a real release key:

```powershell
keytool -genkey -v -keystore $HOME\voltplan-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias voltplan
```

then create `android/key.properties` (git-ignored; back up the `.jks` and its passwords — losing them means
you can never update the app):

```
storePassword=<password>
keyPassword=<password>
keyAlias=voltplan
storeFile=C:/Users/<you>/voltplan-release.jks
```

### Android SDK licences

`flutter doctor` may warn that licences are not accepted. Builds worked here regardless; if yours fails, run
`flutter doctor --android-licenses` and accept them.

## 4. Known limits of this deployment

* One shared key, no per-user accounts or data separation: everyone with the APK sees every project.
* Database schema changes after the first deploy need migrations (Alembic is not set up); the built-in
  additive migration only runs on SQLite.
* Uploaded plans live on one disk: a single instance only.
* The calculations and the cable-capacity tables are still awaiting an electrician's review
  (`docs/CALCULATION_REVIEW.md`); do not present the output as signed-off.
