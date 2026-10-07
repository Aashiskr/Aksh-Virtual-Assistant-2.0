const DEFAULT_QUERIES = [
  'B.Tech final year internship placement scholarship India',
  'government exam recruitment application engineer graduate Uttar Pradesh Bihar',
  'site:gov.in engineering recruitment application Uttar Pradesh',
  'site:gov.in engineering recruitment application Bihar',
];
const MAX_ITEMS = 8;
const RECENT_WINDOW_MS = 4 * 24 * 60 * 60 * 1000;

function rssUrl(query) {
  const value = encodeURIComponent(query);
  return `https://news.google.com/rss/search?q=${value}&hl=en-IN&gl=IN&ceid=IN:en`;
}

export function careerFeedUrls(env = {}) {
  if (env.CAREER_RSS_URLS) {
    try {
      const configured = JSON.parse(env.CAREER_RSS_URLS);
      if (Array.isArray(configured) && configured.length > 0) {
        return configured.filter(validHttpsUrl).slice(0, 10);
      }
    } catch {
      // Fall through to the safe built-in searches.
    }
  }
  return DEFAULT_QUERIES.map(rssUrl);
}

export function parseCareerFeed(xml) {
  const items = [];
  for (const match of String(xml).matchAll(/<item\b[^>]*>([\s\S]*?)<\/item>/gi)) {
    const block = match[1];
    const title = cleanText(tagValue(block, "title"));
    const link = cleanText(tagValue(block, "link"));
    const source = cleanText(tagValue(block, "source")) || "News source";
    const published = new Date(cleanText(tagValue(block, "pubDate")));
    if (!title || !validHttpsUrl(link)) continue;
    items.push({
      title,
      link,
      source,
      published_at: Number.isNaN(published.getTime())
        ? ""
        : published.toISOString(),
    });
  }
  return items;
}

export async function buildCareerBriefing(env, profile, now = new Date()) {
  const responses = await Promise.allSettled(
    careerFeedUrls(env).map(async (url) => {
      const response = await fetch(url, {
        headers: {
          accept: "application/rss+xml, application/xml, text/xml",
          "user-agent": "Aksh-Career-Briefing/1.0",
        },
      });
      if (!response.ok) {
        throw new Error(`Career feed returned HTTP ${response.status}`);
      }
      return parseCareerFeed(await response.text());
    }),
  );

  const cutoff = now.getTime() - RECENT_WINDOW_MS;
  const seen = new Set();
  const candidates = [];
  for (const response of responses) {
    if (response.status !== "fulfilled") continue;
    for (const item of response.value) {
      const published = item.published_at
        ? new Date(item.published_at).getTime()
        : now.getTime();
      if (published < cutoff) continue;
      const key = normalizeTitle(item.title);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      const classified = classify(item, profile);
      if (classified.score < 2) continue;
      candidates.push({ ...item, kind: classified.kind, score: classified.score });
    }
  }

  candidates.sort((left, right) => {
    if (right.score !== left.score) return right.score - left.score;
    return String(right.published_at).localeCompare(String(left.published_at));
  });
  const items = candidates.slice(0, MAX_ITEMS).map(({ score, ...item }) => item);
  const exams = items.filter((item) => item.kind === "government exam").length;
  const careers = items.length - exams;
  const summary = items.length === 0
    ? "Aaj koi important naya B.Tech career ya government exam update nahi mila."
    : `${exams} government exam/recruitment aur ${careers} career update mile. Apply karne se pehle official portal par details verify karein.`;

  return {
    id: `${now.toISOString().slice(0, 10)}-${simpleHash(items.map((item) => item.title).join("|"))}`,
    generated_at: now.toISOString(),
    profile: safeProfile(profile),
    summary,
    items,
  };
}

export function notificationForBriefing(briefing) {
  const count = briefing.items.length;
  return {
    title: count === 0
      ? "Aksh: aaj koi important naya alert nahi"
      : `Aksh: ${count} career/exam update${count === 1 ? "" : "s"}`,
    body: count === 0
      ? "Kal 11 baje phir check karunga."
      : truncate(briefing.items[0].title, 150),
  };
}

function classify(item, profile) {
  const text = `${item.title} ${item.source}`.toLowerCase();
  const examWords = [
    "government", "govt", "recruitment", "vacancy", "exam", "apply",
    "application", "notification", "uppsc", "bpsc", "ssc", "upsc",
    "railway", "rrb", "psu", "engineer", "apprentice",
  ];
  const careerWords = [
    "b.tech", "btech", "engineering", "internship", "placement", "career",
    "scholarship", "graduate", "fresher", "campus", "trainee", "hiring",
  ];
  const applicationWords = [
    "application", "apply", "registration", "form", "notification",
    "recruitment", "vacancy", "vacancies", "hiring", "apprentice",
  ];
  const otherStateWords = [
    "andhra pradesh", "assam", "chhattisgarh", "gujarat", "haryana",
    "himachal pradesh", "jharkhand", "karnataka", "kerala", "madhya pradesh",
    "maharashtra", "odisha", "punjab", "rajasthan", "tamil nadu",
    "telangana", "uttarakhand", "west bengal", "wbpsc",
  ];
  const regionWords = [
    "uttar pradesh", " u.p.", " up ", "bihar", "india", "national",
    ...(profile?.regions || []).map((value) => String(value).toLowerCase()),
  ];
  const targetsUpOrBihar = text.includes("uttar pradesh")
    || /\buppsc\b|\bupsssc\b|\bbihar\b|\bbpsc\b|\bbtsc\b/.test(text);
  if (!targetsUpOrBihar && otherStateWords.some((word) => text.includes(word))) {
    return { kind: "career", score: 0 };
  }
  const examScore = wordScore(text, examWords);
  const careerScore = wordScore(text, careerWords);
  const applicationScore = wordScore(text, applicationWords);
  const regionScore = Math.min(wordScore(` ${text} `, regionWords), 2);
  const kind = examScore >= careerScore ? "government exam" : "career";
  if (examScore === 0 && careerScore === 0) {
    return { kind, score: 0 };
  }
  if (kind === "government exam" && applicationScore === 0) {
    return { kind, score: 0 };
  }
  if (kind === "government exam"
      && /\b(upcoming|expected|out soon)\b/.test(text)
      && !/\b(open|opened|released|started|begins)\b/.test(text)) {
    return { kind, score: 0 };
  }
  return { kind, score: Math.max(examScore, careerScore) + regionScore };
}

function wordScore(text, words) {
  return words.reduce((score, word) => score + (text.includes(word) ? 1 : 0), 0);
}

function safeProfile(profile = {}) {
  return {
    course: "B.Tech",
    year: 4,
    branch: typeof profile.branch === "string" ? profile.branch.slice(0, 40) : "all",
    regions: ["Uttar Pradesh", "Bihar", "All India"],
    timezone: "Asia/Kolkata",
    delivery_hour: 11,
  };
}

function tagValue(block, tag) {
  const match = block.match(new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)<\\/${tag}>`, "i"));
  return match ? match[1] : "";
}

function cleanText(value) {
  return decodeEntities(
    String(value)
      .replace(/^<!\[CDATA\[|\]\]>$/g, "")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim(),
  );
}

function decodeEntities(value) {
  const named = {
    amp: "&", apos: "'", gt: ">", lt: "<", quot: '"', nbsp: " ",
  };
  return value.replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (match, entity) => {
    if (entity[0] === "#") {
      const hexadecimal = entity[1]?.toLowerCase() === "x";
      const number = Number.parseInt(entity.slice(hexadecimal ? 2 : 1), hexadecimal ? 16 : 10);
      return Number.isFinite(number) ? String.fromCodePoint(number) : match;
    }
    return named[entity.toLowerCase()] ?? match;
  });
}

function normalizeTitle(title) {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function truncate(value, length) {
  return value.length <= length ? value : `${value.slice(0, length - 1)}…`;
}

function simpleHash(value) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function validHttpsUrl(value) {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}
