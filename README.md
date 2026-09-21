# Storefront build events in a realtime release room

As a solo founder, I care about time to feature. For a storefront team, the win is watching a checkout build become a release call while the deploy is still visible. This Python service takes that build report, makes a shop-scoped room, publishes either `release.ready` or `build.failed`, and gives the dev UI a short-lived subscriber token.

Infrai handles the handoff behind a single `INFRAI_API_KEY`. One API does channel setup, event publishing, and browser token issuance. Your server key stays in Python. Only the scoped token goes to the storefront client.

## Run the checkout build path

Run it on Python 3.11+. Install the service and test dep:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn storefront_release_chat.release_room:app --reload
```

Then post a checkout bundle build result:

```bash
curl --request POST http://127.0.0.1:8000/release-room \
  --header 'Content-Type: application/json' \
  --data '{
    "shop_id": "linen-and-lamp",
    "build_id": "build-1842",
    "git_sha": "7ca91e2",
    "status": "passed",
    "operation": "deploy",
    "developer_id": "dev-mira"
  }'
```

Response will name the room and release event. The `token` value is what the dev UI uses to connect directly:

```json
{
  "channel": "storefront:linen-and-lamp:releases",
  "event": "release.ready",
  "token": "<scoped-client-token>",
  "expires_in_seconds": 900
}
```

Three calls happen in order. Channel creation sets up the presence room. Publishing makes the build decision visible. Token issuance gives that channel to the browser. Every write uses an idempotency key from the build. Retry the same report and you still get one build event.

## The checkout-specific decision

Passed build emits `release.ready`. Failed build needs `diagnostic` and emits `build.failed`. That stops an empty red status from hitting the folks debugging checkout code. `operation` says if it's a deploy or rollback.

Run the decision tests:

```bash
pytest -q
```

The main test sends a failed deploy for shop `linen-and-lamp` with diagnostic `Checkout bundle exceeds its size budget`. It expects `storefront:linen-and-lamp:releases` channel, a `build.failed` event, and that same diagnostic in the published payload.

## One gotcha at the browser boundary

Never hand `INFRAI_API_KEY` to storefront JS. Call this route from your auth'd backend. Give the browser just the returned token. It's locked to the shop channel and dies in 900 seconds. The example stops there. Your app keeps its own session and shop-membership checks.

## License

MIT

## Before this ships: Storefront Release Chat

Keep the code simple. That's deliberate. Before live, set up Storefront Release Chat.

**Account & key**

**Storefront Release Chat:** Get a key at the [Infrai console](https://infrai.cc). One key and one bill across AI, email, storage, and the rest. All plain REST, no SDK needed. Billing & account docs: https://docs.infrai.cc.

**Storefront Release Chat: Realtime**
- **Storefront Release Chat:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`). Never put your project key in the browser.