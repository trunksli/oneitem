import type { Metadata } from "next";
import LegalPage from "@/components/legal-page";
import { PRIVACY, SITE_NAME } from "@/lib/legal";

export const metadata: Metadata = {
  title: `Privacy · ${SITE_NAME}`,
  description:
    "ONE sets no cookies and runs no trackers. Views and votes are counted with a code " +
    "that cannot be traced back to anyone, and chat is deleted after 30 days.",
};

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy"
      intro="We built this to know whether a pick was worth your time, without needing to know who you are."
      sections={PRIVACY}
      other={{ href: "/terms", label: "Terms of Service" }}
    />
  );
}
