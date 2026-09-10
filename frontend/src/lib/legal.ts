/**
 * Legal and disclosure copy for ONE, kept as data so the routes stay
 * presentational and a wording change never has to be made twice.
 *
 * Adapted from the Balmody (Verse) documents by the same operator. The structure,
 * the plain-language approach, and the standard clauses -- warranties,
 * liability, indemnity, governing law, severability -- carry over. Everything
 * describing what the service DOES has been rewritten, because the products
 * handle data very differently: Verse stores nothing, while ONE keeps a public
 * chat, anonymous votes and anonymous engagement counts.
 *
 * NOT LEGAL ADVICE. Drafted by the engineering side for review by counsel before
 * launch; see LEGAL-REVIEW.md at the repo root for what the reviewer is asked to
 * check. Statements of fact about the system are listed here, and each must be
 * re-checked whenever the code it describes changes:
 *
 *   - Chat: stored with an optional display name, shown for the UTC day, and
 *     deleted after 30 days (backend/app/queries.py purge_expired,
 *     COMMENT_RETENTION_DAYS).
 *   - Votes and engagement: keyed by a daily-salted hash of network address and
 *     browser type (backend/app/visitors.py). The address is never stored; each
 *     earlier day's salt is deleted.
 *   - ONE sets no cookies and loads no analytics or advertising scripts. Fonts are
 *     self-hosted by next/font, so no request goes to Google Fonts. YouTube
 *     players use youtube-nocookie.com.
 *   - Third-party text: at most 3,000 characters are kept, only until the item is
 *     scored, then cleared (backend/app/previews.py SCORING_TEXT_LIMIT).
 */

export const SITE_NAME = "ONE";

export const LAST_UPDATED = "10 September 2026";

/**
 * Shared with Balmody until ONE has its own name and address -- confirmed by the
 * operator, 9 September 2026. This is where people exercise privacy rights and
 * send takedown requests, so it must keep receiving mail. It appears nowhere
 * else in the codebase; change it here.
 */
export const CONTACT_EMAIL = "balmodyco@gmail.com";

export const GOVERNING_LAW = "the State of California, United States";

export const YOUTUBE_TERMS_URL = "https://www.youtube.com/t/terms";
export const GOOGLE_PRIVACY_URL = "https://policies.google.com/privacy";

export interface LegalSection {
  heading: string;
  body: string[];
}

export const AI_DISCLOSURE =
  "The short previews and the “why this one” notes on ONE are written by an " +
  "AI model (Google Gemini) from the source material, and are not checked by a " +
  "person before they appear. They can be wrong, and can be wrong confidently. " +
  "The original work is always one click away; please treat it, not our summary, " +
  "as the authority.";

export const NO_COOKIES =
  "ONE sets no cookies. There are no advertising networks, no analytics services, " +
  "no session recording, and no third-party trackers on this site.";

export const ANONYMOUS_COUNTS =
  "We count views, plays and votes, because the whole point of ONE is to learn " +
  "whether a pick was worth your time. So that one person is not counted twice in a " +
  "day, our server turns your network address and browser type into a code, using a " +
  "random value that is destroyed every day. The address itself is never stored, " +
  "and once that day's value is destroyed, not even we can connect the code back to " +
  "you or to your visits on any other day.";

export const TERMS: LegalSection[] = [
  {
    heading: "What this is",
    body: [
      `${SITE_NAME} features one piece of work at a time, four times a day — a ` +
        "video, an article, or a piece of audio, chosen because we think it is " +
        "exceptional and because you might not have found it on your own.",
      "The work we feature is made by other people. We link to it and embed it using " +
        "the official players its publishers provide. We do not host it.",
    ],
  },
  {
    heading: "Who can use this",
    body: [
      "You must be at least 13 years old to use the service. If you are under 18, " +
        "please use it with a parent or guardian who agrees to these terms on your behalf.",
      "We do not verify age, because doing so would mean collecting identity " +
        "information we have deliberately chosen not to hold.",
    ],
  },
  {
    heading: "The work belongs to its creators",
    body: [
      "Every video, article and recording featured here remains the property of " +
        "whoever made it. Alongside each one we show its title, the image its publisher " +
        "chose for sharing, a short preview, and a link or an embedded player. The " +
        "preview is either the first lines of the piece or a brief summary.",
      "If you created something we feature and would rather we did not, write to " +
        `${CONTACT_EMAIL} and we will remove it. You do not need to give a reason.`,
      "For a formal copyright complaint, please include: the work you believe is " +
        "infringed; the page on ONE where it appears; how to contact you; a statement " +
        "that you believe in good faith the use is not authorised; and a statement that " +
        "the information in your notice is accurate and that you are the rights holder " +
        "or are authorised to act for them.",
      "Our crawler identifies itself as ONE-curator, follows the rules publishers set " +
        "in robots.txt, and keeps no full copy of what it reads.",
    ],
  },
  {
    heading: "AI-written previews and notes",
    body: [AI_DISCLOSURE],
  },
  {
    heading: "Videos from YouTube",
    body: [
      "Some of the videos we feature are provided through YouTube API Services. By " +
        "watching them here, you agree to be bound by the YouTube Terms of Service, " +
        `${YOUTUBE_TERMS_URL}.`,
    ],
  },
  {
    heading: "The chat",
    body: [
      "The Daily Lobby is public. Anything you post there, and the display name you " +
        "choose, can be read by anyone visiting the site.",
      "Please do not post anything unlawful, harassing, hateful, or sexually explicit; " +
        "anything that shares another person's private information; spam or " +
        "advertising; or anything you do not have the right to share.",
      "You keep ownership of what you write. By posting it, you let us display it on " +
        "ONE for as long as we keep it. Messages are shown for the day they are posted " +
        "and are deleted after 30 days. We may remove any message, at any time, for " +
        "any reason.",
      `To report a message, write to ${CONTACT_EMAIL} with its text and roughly when ` +
        "it was posted.",
    ],
  },
  {
    heading: "Acceptable use",
    body: [
      "Please use the service as intended. Do not attempt to overload it, to vote or " +
        "post through automated means, to interfere with how picks are counted, or to " +
        "access it in ways designed to get around its limits.",
      "We limit how often any one visitor can post, vote or send activity, to keep the " +
        "service usable and the counts honest.",
    ],
  },
  {
    heading: "Links and services we do not control",
    body: [
      "ONE links to websites and embeds players run by other companies. We do not " +
        "control them and are not responsible for their content, availability, or " +
        "practices. When you follow a link or press play, their terms and privacy " +
        "policies apply.",
      "We rely on third-party providers to host the service and to evaluate and " +
        "summarise the work we feature. Their availability is outside our control.",
    ],
  },
  {
    heading: "Suspending or ending access",
    body: [
      "We may limit, suspend, or end access at any time, including where use appears " +
        "abusive or where continuing would put the service at risk. Because there are " +
        "no accounts, this generally means blocking a pattern of requests rather than a " +
        "person.",
      "We may also stop offering the service entirely. It is free, and we make no " +
        "promise that it will continue to exist.",
    ],
  },
  {
    heading: "Disclaimer of warranties",
    body: [
      "The service is provided “as is” and “as available”, without " +
        "warranties of any kind, whether express or implied, including but not limited " +
        "to any implied warranties of merchantability, fitness for a particular purpose, " +
        "accuracy, or non-infringement.",
      "We do not warrant that the service will be uninterrupted, timely, secure, or " +
        "error-free, that any pick, preview or note will be accurate, appropriate, or to " +
        "your taste, or that defects will be corrected.",
    ],
  },
  {
    heading: "Limitation of liability",
    body: [
      "To the fullest extent permitted by law, we are not liable for any indirect, " +
        "incidental, special, consequential, or punitive damages, or any loss of data, " +
        "use, or goodwill, arising out of your use of or inability to use the service.",
      "Where liability cannot be excluded, it is limited to the greater of the amount " +
        "you have paid us, which is nothing, or one hundred US dollars.",
      "Nothing in these terms excludes or limits liability where doing so would be " +
        "unlawful, including for death or personal injury caused by negligence, or for fraud.",
    ],
  },
  {
    heading: "Indemnity",
    body: [
      "If someone brings a claim against us because of how you used the service — for " +
        "example by posting something in the chat that these terms prohibit, or in breach " +
        "of the law or the rights of others — you agree to cover the reasonable costs " +
        "and damages that result.",
      "This does not apply to claims arising from our own wrongdoing, and it does not " +
        "apply where the law does not allow it.",
    ],
  },
  {
    heading: "Changes",
    body: [
      "We may update these terms. The date at the top of this page shows when they last " +
        "changed. Continuing to use the service after a change means you accept it.",
    ],
  },
  {
    heading: "Governing law and disputes",
    body: [
      `These terms are governed by the laws of ${GOVERNING_LAW}, without regard to its ` +
        "conflict of law rules. Any dispute will be brought in the courts of that " +
        "jurisdiction.",
      "If you live somewhere whose consumer law gives you the right to bring a claim " +
        "locally, or protections that cannot be waived, nothing here takes that away.",
      "Before starting anything formal, please write to us. Most things are easier to " +
        "fix than to litigate.",
    ],
  },
  {
    heading: "The rest",
    body: [
      "If any part of these terms turns out to be unenforceable, the rest still applies, " +
        "and the unenforceable part is treated as narrowed to whatever the law does allow.",
      "Not enforcing something once does not mean we give up the right to enforce it " +
        "later. These terms, together with the privacy policy, are the whole agreement " +
        "between us about the service.",
    ],
  },
  {
    heading: "Contact",
    body: [`Questions about these terms: ${CONTACT_EMAIL}.`],
  },
];

export const PRIVACY: LegalSection[] = [
  {
    heading: "The short version",
    body: [
      NO_COOKIES,
      ANONYMOUS_COUNTS,
      "There are no accounts. We never ask for your name, email address, or location.",
      "The one thing you can give us is a chat message, which is public and is deleted " +
        "after 30 days.",
    ],
  },
  {
    heading: "What we keep",
    body: [
      "Chat messages, with the display name you chose if you chose one. They are public, " +
        "shown for the day they are posted, and deleted after 30 days.",
      "Your answer to “Was this new to you?”, stored against the pick it was " +
        "about and the anonymous daily code described above. Answering again changes your " +
        "answer rather than adding another.",
      "Anonymous activity: that a pick was viewed, played, read, opened at its source, " +
        "or shared, stored against the same daily code.",
      "Nothing else. We keep no account, profile, browsing history, or record of who you are.",
    ],
  },
  {
    heading: "How the anonymous code works",
    body: [
      "When you vote or when a pick is viewed, our server combines your network address " +
        "and your browser's name with a secret random value, and scrambles the result " +
        "into a code that cannot be reversed. We store only the code.",
      "The random value changes every day, and each earlier day's value is deleted. That " +
        "makes today's codes impossible to link to yesterday's, and impossible to trace " +
        "back to an address, including by us.",
      "We also use the code to limit how often anyone can post or vote, which keeps the " +
        "service usable and the counts honest.",
    ],
  },
  {
    heading: "What is stored on your device",
    body: [
      "Your display name, if you set one, and the answers you gave, so the button you " +
        "chose stays highlighted. These live in your browser's own storage. The name is " +
        "sent to us only as part of a message you choose to post.",
      "Clearing your browser data removes them. We cannot recover them for you, because " +
        "we never had them.",
    ],
  },
  {
    heading: "Embedded players",
    body: [
      "Videos from YouTube play in YouTube's privacy-enhanced mode (youtube-nocookie.com), " +
        "which YouTube describes as not storing information about visitors unless they " +
        "play the video. Once you press play, you are using YouTube, and YouTube's terms " +
        `and Google's privacy policy apply: ${GOOGLE_PRIVACY_URL}.`,
      "Some videos are provided through YouTube API Services, which we use only to read " +
        "public information about videos. We never access your YouTube or Google account.",
      "When you follow a link to the original work, you leave ONE and that site's own " +
        "privacy practices apply.",
    ],
  },
  {
    heading: "Who else is involved",
    body: [
      "Our hosting provider runs the servers and database that ONE uses.",
      "We send the public work we are evaluating — titles, descriptions, and the " +
        "opening of an article or transcript — to Google (Gemini) to score it and " +
        "write the previews. We never send your messages, your votes, or anything about you.",
      "We use no advertising networks, analytics vendors, or data brokers, and we sell " +
        "nothing to anyone.",
    ],
  },
  {
    heading: "Server logs",
    body: [
      "Our hosting provider records basic technical information for every request, such " +
        "as the time, the response status, and the network address it came from. This is " +
        "standard for any website and is used to keep the service running and to limit " +
        "abuse. Those logs are held by the provider on its own schedule.",
    ],
  },
  {
    heading: "Children",
    body: [
      `${SITE_NAME} is not directed at children under 13, and we do not knowingly collect ` +
        "information from them. If you believe a child has posted in the chat, write to us " +
        "and we will remove it.",
    ],
  },
  {
    heading: "How long anything is kept",
    body: [
      "Chat messages: 30 days. The daily random value: one day. Anonymous votes and " +
        "activity: kept, because after that day they cannot be connected to anyone. Server " +
        "logs: on our hosting provider's standard schedule.",
      "Text from the articles and videos we evaluate is kept only until it has been " +
        "scored, and never in full.",
    ],
  },
  {
    heading: "Where it is processed",
    body: [
      "Our hosting provider and our AI provider operate internationally, including in the " +
        "United States, so requests may be processed outside the country you are in.",
    ],
  },
  {
    heading: "Security",
    body: [
      "Traffic is encrypted in transit, and our provider keys are held on the server and " +
        "never appear in the page you load. The strongest protection is structural: we " +
        "hold no accounts, no email addresses, and no network addresses, so there is very " +
        "little here worth stealing.",
      "No service can promise perfect security, and we do not.",
    ],
  },
  {
    heading: "Your rights",
    body: [
      "Privacy laws including the California Consumer Privacy Act give you rights to " +
        "access, correct, and delete personal information a business holds about you, and " +
        "to opt out of its sale or sharing.",
      "We sell nothing and share nothing for advertising. Because votes and activity are " +
        "stored under a daily code we cannot trace back to you, there is no profile to " +
        "hand over. If you want a chat message removed, write to us with its text and " +
        "roughly when you posted it.",
    ],
  },
  {
    heading: "Changes to this policy",
    body: [
      "If this policy changes, the date at the top of the page changes with it. If we " +
        "ever begin collecting something we do not collect today, we will say so here " +
        "plainly rather than by quietly broadening the wording.",
    ],
  },
  {
    heading: "Contact",
    body: [
      `Questions about privacy, or to exercise a right described above: ${CONTACT_EMAIL}.`,
    ],
  },
];
