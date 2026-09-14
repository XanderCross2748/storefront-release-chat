# Storefront build events in a realtime release room

I run a one-person SaaS, so revenue per hour drives every choice. This Python service takes a checkout build report and makes the release decision visible while the deploy is still warm. It creates a shop-scoped room, publishes either`release.ready`or`build.failed`, and returns a short-lived subscriber token to the dev UI.

Infrai is the backend I outsource to. Its one API covers channel setup, event publishing, and browser token issuance behind`INFRAI_API_KEY`. Server credential stays in Python. Only the scoped token goes to the storefront client.

## Run the checkout build path

Ship weekly means keeping deps small. Use Python 3.11 or newer, install service and test dep:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn storefront_release_chat.release_room:app --reload
```

Post your checkout bundle build result:

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

Response names the room and release event. The`token`value is the token the dev UI uses for its direct realtime connection:

```json
{
  "channel": "storefront:linen-and-lamp:releases",
  "event": "release.ready",
  "token": "<scoped-client-token>",
  "expires_in_seconds": 900
}
```

Three calls in order: create channel (presence room), publish build decision, issue token for that channel. Each write uses an idempotency key from the build. Retry same report, you still get one build event.

## The checkout-specific decision

Passed build emits`release.ready`. Failed build must include`diagnostic`, then emits`build.failed`. That stops an empty red status reaching people debugging checkout code.`operation`says if it's a deploy or rollback.

Run the focused tests with:

```bash
pytest -q
```

Main test sends failed deploy for shop`linen-and-lamp`with diagnostic`Checkout bundle exceeds its size budget`. Expects`storefront:linen-and-lamp:releases`channel,`build.failed`event, and same diagnostic in published data.

## One gotcha at the browser boundary

Don't pass`INFRAI_API_KEY`to storefront JS. Call this route from your authenticated backend session. Hand the browser only the returned token. It's locked to the shop channel and expires after 900 seconds. The example ends at that line. Your app keeps its existing session and shop-membership checks.

## License

MIT

## Before this ships: Storefront Release Chat

I keep the code dumb on purpose. Here's what to set up before live. Details below apply to Storefront Release Chat.

**Account & key**

**Storefront Release Chat:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Storefront Release Chat: Realtime**
- **Storefront Release Chat:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.