import assert from "node:assert/strict";
import test from "node:test";

import {
  buildCareerBriefing,
  notificationForBriefing,
  parseCareerFeed,
} from "../src/briefing.js";
import { fcmMessage } from "../src/fcm.js";

const rss = `<?xml version="1.0"?>
<rss><channel>
  <item>
    <title><![CDATA[UP engineering recruitment applications open &amp; details]]></title>
    <link>https://example.gov.in/recruitment/42</link>
    <pubDate>Mon, 31 Aug 2026 04:00:00 GMT</pubDate>
    <source>Example Recruitment Board</source>
  </item>
</channel></rss>`;

test("career RSS parser preserves safe source details", () => {
  const items = parseCareerFeed(rss);
  assert.equal(items.length, 1);
  assert.equal(
    items[0].title,
    "UP engineering recruitment applications open & details",
  );
  assert.equal(items[0].link, "https://example.gov.in/recruitment/42");
  assert.equal(items[0].source, "Example Recruitment Board");
});

test("FCM payload is a visible high-priority career data message", () => {
  const briefing = {
    id: "2026-08-31-abcd",
    items: [{ title: "Graduate engineer applications open" }],
  };
  const notification = notificationForBriefing(briefing);
  const payload = fcmMessage("phone-token", briefing, notification);
  assert.equal(payload.message.data.type, "career_briefing");
  assert.equal(payload.message.android.priority, "high");
  assert.match(payload.message.data.title, /1 career\/exam update/);
});

test("briefing keeps UP/Bihar applications and rejects other-state notices", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(`
    <rss><channel>
      <item>
        <title>UPPSC engineer recruitment applications open</title>
        <link>https://uppsc.example.gov.in/apply</link>
        <pubDate>Mon, 31 Aug 2026 04:00:00 GMT</pubDate>
        <source>UPPSC</source>
      </item>
      <item>
        <title>WBPSC engineer recruitment applications open</title>
        <link>https://wbpsc.example.gov.in/apply</link>
        <pubDate>Mon, 31 Aug 2026 04:00:00 GMT</pubDate>
        <source>WBPSC</source>
      </item>
    </channel></rss>
  `, { status: 200 });
  try {
    const briefing = await buildCareerBriefing(
      {},
      { regions: ["Uttar Pradesh", "Bihar", "All India"] },
      new Date("2026-08-31T06:00:00Z"),
    );
    assert.deepEqual(
      briefing.items.map((item) => item.title),
      ["UPPSC engineer recruitment applications open"],
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
