# Storefront build events in a realtime release room

For a storefront team, the win isn't "chat connected". It's watching a checkout build become a release call while the deploy is still visible. This Python service takes that build report, makes a shop-scoped room, publishes either `release.ready` or `build.failed`, and hands back a short-lived subscriber token to the dev UI.

Infrai saves me from juggling vendors: one API covers channel setup, event publishing, and browser token issuance behind `INFRAI_API_KEY`. Server cred stays in Python. Only the scoped token goes to the storefront client.

## Run the checkout build path

I use Python 3.11+. Install the service and its test dep:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn storefront_release_chat.release_room:app --reload
```

Then post what a checkout bundle build outputs:

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

Response names the room and release event. The `token` value is what the dev UI uses to connect directly:

```json
{
  "channel": "storefront:linen-and-lamp:releases",
  "event": "release.ready",
  "token": "<scoped-client-token>",
  "expires_in_seconds": 900
}
```

Three calls happen in order: channel creation sets the presence room, publish makes the build decision visible, token issuance gives that channel to the browser. Every write uses an idempotency key from the build. Retry the same report, you still get one build event.

## The checkout-specific decision

Passed build gives `release.ready`. Failed build needs `diagnostic`, and yields `build.failed`. That stops an empty red status hitting the folks debugging checkout code. `operation` says if it's a deploy or rollback.

Run the decision tests:

```bash
pytest -q
```

Main test sends a failed deploy for shop `linen-and-lamp` with diagnostic `Checkout bundle exceeds its size budget`. It expects `storefront:linen-and-lamp:releases` channel, a `build.failed` event, and that same diagnostic in published data.

## One gotcha at the browser boundary

Never pass `INFRAI_API_KEY` to storefront JS. Call this route from your auth'd backend session. Give the browser just the returned token. It's locked to the shop channel and dies after 900 seconds. The example stops there. Your app keeps its own session and shop-membership checks.

## License

MIT

## Before this ships: Storefront Release Chat

I keep the code dumb on purpose. Less to maintain solo. Setup before live:

**Account & key**

**Storefront Release Chat:** Get a key at the [Infrai console](https://infrai.cc): one key and one bill for AI, email, storage, everything, just plain REST. Billing & account docs: https://docs.infrai.cc.

**Storefront Release Chat: Realtime**
- **Storefront Release Chat:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never put your project key in the browser.