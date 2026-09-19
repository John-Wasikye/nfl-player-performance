"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { AUTHOR, linkProps } from "@/lib/site";

type Status = "idle" | "sending" | "sent" | "error" | "too-fast";

// Anyone filling in three fields takes longer than this. A bot posting straight away doesn't.
const MIN_MILLISECONDS = 2500;

export function contactEndpoint(): string {
  return process.env.NEXT_PUBLIC_CONTACT_ENDPOINT ?? "";
}

const fieldClass =
  "mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

export function ContactForm() {
  const endpoint = contactEndpoint();
  const openedAt = useRef(0);
  const [status, setStatus] = useState<Status>("idle");

  useEffect(() => {
    openedAt.current = Date.now();
  }, []);

  if (!endpoint) {
    return (
      <p className="text-sm text-muted">
        The contact form isn&apos;t switched on yet. In the meantime you can reach me through{" "}
        <a className="text-accent underline underline-offset-2" {...linkProps(AUTHOR.github)}>
          GitHub
        </a>
        .
      </p>
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);

    // Real visitors never see this field, so anything in it came from a script.
    if (data.get("website")) {
      setStatus("sent");
      return;
    }
    if (Date.now() - openedAt.current < MIN_MILLISECONDS) {
      setStatus("too-fast");
      return;
    }

    setStatus("sending");
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          name: data.get("name"),
          email: data.get("email"),
          message: data.get("message"),
        }),
      });
      if (!response.ok) throw new Error(`status ${response.status}`);
      form.reset();
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="contact-name" className="text-sm font-medium">
            Name
          </label>
          <input
            id="contact-name"
            name="name"
            type="text"
            required
            maxLength={100}
            autoComplete="name"
            className={fieldClass}
          />
        </div>
        <div>
          <label htmlFor="contact-email" className="text-sm font-medium">
            Your email
          </label>
          <input
            id="contact-email"
            name="email"
            type="email"
            required
            maxLength={200}
            autoComplete="email"
            className={fieldClass}
          />
        </div>
      </div>
      <div>
        <label htmlFor="contact-message" className="text-sm font-medium">
          Message
        </label>
        <textarea
          id="contact-message"
          name="message"
          required
          minLength={10}
          maxLength={3000}
          rows={6}
          className={fieldClass}
        />
      </div>

      <div aria-hidden="true" className="absolute left-[-9999px] h-0 w-0 overflow-hidden">
        <label htmlFor="contact-website">Leave this empty</label>
        <input id="contact-website" name="website" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <button
          type="submit"
          disabled={status === "sending"}
          className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-accent-fg hover:opacity-90 disabled:opacity-60"
        >
          {status === "sending" ? "Sending..." : "Send message"}
        </button>
        {status === "sent" && (
          <p role="status" className="text-sm text-up">
            Thanks, your message was sent.
          </p>
        )}
        {status === "error" && (
          <p role="alert" className="text-sm text-down">
            That didn&apos;t send. Please try again, or reach me through GitHub.
          </p>
        )}
        {status === "too-fast" && (
          <p role="alert" className="text-sm text-down">
            That was quick. Please check your message and send it again.
          </p>
        )}
      </div>

      <p className="text-xs text-muted">
        Your name, email and message are sent to me through a form service and used only to reply.
      </p>
    </form>
  );
}
