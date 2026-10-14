# Deploying the backend and building the release APK

The backend is a Docker container (`backend/Dockerfile`) that needs **PostgreSQL** and a few environment
variables. `render.yaml` describes it for Render on **free plans** (web service + free Postgres, no disk), which is
meant for trying the app out; Railway and Fly.io work with the same Dockerfile and variables.

## 0. What is protected, and what is not

* The backend has **no user accounts**. A **shared API key** gates every route except `/api/health`
  (`X-API-Key` header). It stops strangers creating projects, uploading files and spending your AI credit.
* The key is compiled into the APK, so **anyone who unpacks the APK can read it**. Hand the APK only to people
  who should have access, and rotate the key (redeploy the backend + rebuild the APK) if it leaks.
* With a real AI provider in production the backend **refuses to start without `API_KEY`**.
* On the free setup, uploaded plans live on temporary storage and disappear on every restart (see section 4).

## 1. Make the API key

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Keep it in a password manager. Do not commit it, paste it into chats or put it in a file in the repository.

## 2. Deploy on Render

1. Push the branch you want to run (the blueprint uses `remediation/phase1-geometry`; change `branch:` in
   `render.yaml` to `main` once merged).
2. Render dashboard → **New → Blueprint** → select this repository → it reads `render.yaml`.
3. Check that the service and the database both show as **Free** (⚠ unverified from here; Render may allow only
   one free database per workspace). Nothing in this blueprint should have a price.
4. When prompted, enter **`API_KEY`** (from step 1). Leave `GEMINI_API_KEY` / `OPENAI_API_KEY` empty for now.
5. Wait for the deploy, then open `https://<service>.onrender.com/api/health`. Expected:
   `{"status":"ok", ... "environment":"production", "ai_provider":"mock" ...}`.

`AI_PROVIDER` is not given a value in `render.yaml` (Render would re-apply it on every sync and silently switch you back
to mock data); the Blueprint screen asks for it (`mock`, `gemini` or `openai`) and it is edited in the dashboard afterwards.
`mock` returns the same demo rooms for every upload. To read real plans set
`AI_PROVIDER=gemini` (or `openai`) **and** the matching key in the service's environment, then redeploy.

### Free-tier behaviour to expect

* **Cold starts.** The free web service sleeps after about 15 minutes idle; the first request afterwards can take
  around a minute. The app handles this itself: before the first request (and after 10 idle minutes) it polls
  `/health` until the server answers, shows a "Waking the server up…" notice, then sends the real request. A plain
  read that still times out is retried once after another wake-up. Writes (create, upload, analyse, edit) are never
  repeated automatically, so nothing is created twice.
* **Plans disappear.** Uploaded floor plans are kept on the container's temporary disk and are deleted when the
  service restarts, redeploys or sleeps. The project data stays (it is in Postgres), but the plan image does not:
  upload the plan again before analysing or editing rooms.
* **The database expires** after a limited time (30 days at the time of writing) and is deleted without a backup.

### Moving to real use

Switch `plan:` of the web service to a paid plan, add a persistent disk
(`disk: {name: voltplan-uploads, mountPath: /app/uploads, sizeGB: 1}`) or move uploads to object storage, and use a
paid database.

### Other hosts

Same image, same variables: `DATABASE_URL` (Postgres), `API_KEY`, `APP_ENV=production`, `DEBUG=False`,
`AI_PROVIDER`, optional provider keys, and a persistent volume mounted at `/app/uploads`. The container listens on `$PORT`
(default 8000) and exposes `/api/health` for health checks. Put it behind HTTPS (hosts do this for you).

### One-click check

```powershell
.\scripts\check_backend.ps1          # alive? locked? key works? AI provider ready?
.\scripts\check_backend.ps1 -Full    # also runs one real plan analysis (one AI call) and deletes it
```

It finds your key in `$env:VOLTPLAN_API_KEY` or `~\voltplan_api_key.txt`, never prints it, waits for a sleeping free server
to wake up, and exits with code 1 if anything fails. Use `-ApiUrl http://127.0.0.1:8000/api` for a local backend.

### Verify protection from outside

```powershell
curl https://<host>/api/projects                                  # -> 401 Invalid or missing API key.
curl -H "X-API-Key: <key>" https://<host>/api/projects            # -> []
```

## 2b. Turn on the real AI (Gemini)

The backend starts with `AI_PROVIDER=mock`. To read real plans:

1. Create an API key in Google AI Studio (https://aistudio.google.com/apikey). Keep it secret.
2. In Render: service **voltplan-api → Environment**:
   * set `AI_PROVIDER` to `gemini`
   * paste the key into `GEMINI_API_KEY`
   * leave `GEMINI_MODEL` unset (default `gemini-3.5-flash-lite`, tested on a drawn plan) unless the check below says otherwise
   * **Save, rebuild, and deploy**.
3. Check it, **without analysing a plan**:

   ```powershell
   curl -H "X-API-Key: <your API_KEY>" https://<host>/api/ai/check
   ```

   You want `"ok": true` and `"model_available": true`. If the model is not available the answer lists the models
   your key can use: set `GEMINI_MODEL` to one of them (a recent *flash* model is a good start; a *pro* model reads
   drawings better but is slower and costs more) and redeploy.
4. Upload a plan in the app and analyse it. Expect corrections: real readings often fail the geometry checks at first;
   fix the rooms and doors in the Rooms & Doors editor and regenerate.

Things to know:

* Every analysis sends the plan image to Google. Check Google's terms for how your plan data is handled, especially on
  free tiers, before uploading client drawings.
* Every analysis is one paid API call (free tiers have rate limits). The shared `API_KEY` is what keeps strangers from
  triggering them.
* Errors never contain your Gemini key; failures show Google's own message, e.g. `HTTP 429: Quota exceeded`.
* Temporary provider errors (429, 500, 502, 503, 504, e.g. Gemini's "high demand") are retried twice, after 2 s and 5 s.
* OpenAI works the same way: `AI_PROVIDER=openai`, `OPENAI_API_KEY`, optional `OPENAI_MODEL`.

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
* Uploaded plans live on the container's disk (temporary on the free setup): a single instance only.
* The calculations and the cable-capacity tables are still awaiting an electrician's review
  (`docs/CALCULATION_REVIEW.md`); do not present the output as signed-off.
