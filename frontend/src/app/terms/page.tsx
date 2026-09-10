import type { Metadata } from "next";
import LegalPage from "@/components/legal-page";
import { SITE_NAME, TERMS } from "@/lib/legal";

export const metadata: Metadata = {
  title: `Terms of Service · ${SITE_NAME}`,
  description:
    "The terms under which ONE is provided: the work belongs to its creators, previews " +
    "are AI-written, and the chat is public.",
};

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of Service"
      intro="Plain language, because nobody reads these otherwise."
      sections={TERMS}
      other={{ href: "/privacy", label: "Privacy" }}
    />
  );
}
