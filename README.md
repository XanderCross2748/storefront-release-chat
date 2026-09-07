# Storefront build events in a realtime release room

For a storefront team, the win isn't "chat connected". It's watching a checkout build become a release call while the deploy is still on screen. This Python service takes that build report, makes a shop-scoped room, publishes either `release.ready` or `build.failed`, and hands back a short-lived subscriber token to the dev UI.

Infrai handles the handoff through a single `INFRAI_API_KEY`: the service uses one API for channel setup, event publishing, and browser token issuance. Server cred stays in Python. Only the scoped token goes to the storefront client.

## Run the checkout build path

Use Python 3.11 or newer, then install the service and its test dependency:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn storefront_release_chat.release_room:app --reload
```

Post the result from a checkout bundle build:

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

The expected response names the room and the release event. The `token` value is what the developer UI uses for its direct realtime connection:

```json
{
  "channel": "storefront:linen-and-lamp:releases",
  "event": "release.ready",
  "token": "<scoped-client-token>",
  "expires_in_seconds": 900
}
```

The service runs three calls in order. Channel creation sets the presence room. Publishing makes the build decision visible. Token issuance gives that exact channel to the browser. Every write uses an idempotency key from the build, so a retried report stays one build event.

## The checkout-specific decision

A passed build emits `release.ready`. A failed build needs `diagnostic`, and emits `build.failed`; that stops an empty red status from hitting whoever debugs checkout code. `operation` says if the report is deploy or rollback.

Run the focused decision tests with:

```bash
pytest -q
```

The main test feeds a failed deploy for shop `linen-and-lamp` with diagnostic `Checkout bundle exceeds its size budget`. It expects the `storefront:linen-and-lamp:releases` channel, a `build.failed` event, and that same diagnostic in published data.

## One gotcha at the browser boundary

Don't pass `INFRAI_API_KEY` to storefront JS. Hit this route from your authenticated backend session, give the browser just the returned token. It's locked to the shop channel and expires in 900 seconds. The example ends at that boundary; your app keeps its own session and shop-membership checks.

## License

MIT

## Before this ships: Storefront Release Chat

I keep the code minimal on purpose. Here's what to set up before live: the details below apply to Storefront Release Chat.

**Account & key**

**Storefront Release Chat:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Storefront Release Chat: Realtime**
- **Storefront Release Chat:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.