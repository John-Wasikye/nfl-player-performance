import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ContactForm } from "@/components/ContactForm";

const ENDPOINT = "https://contact.example.test/send";

function fillIn(container: HTMLElement) {
  return async (user: ReturnType<typeof userEvent.setup>) => {
    await user.type(screen.getByLabelText("Name"), "Sam Reader");
    await user.type(screen.getByLabelText("Your email"), "sam@example.com");
    await user.type(screen.getByLabelText("Message"), "Nice project, a question about the model.");
    return container;
  };
}

describe("contact form", () => {
  const fetchMock = vi.fn();
  let now = 1_000;

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("NEXT_PUBLIC_CONTACT_ENDPOINT", ENDPOINT);
    now = 1_000;
    vi.spyOn(Date, "now").mockImplementation(() => now);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("says it isn't switched on, and shows no form, when no endpoint is configured", () => {
    vi.stubEnv("NEXT_PUBLIC_CONTACT_ENDPOINT", "");

    render(<ContactForm />);

    expect(screen.getByText(/isn't switched on yet/)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "GitHub" })).toHaveAttribute(
      "href",
      expect.stringContaining("github.com"),
    );
  });

  it("sends the name, email and message as JSON and confirms", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));
    const user = userEvent.setup();
    const { container } = render(<ContactForm />);
    await fillIn(container)(user);
    now = 20_000;

    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("your message was sent"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(ENDPOINT);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      name: "Sam Reader",
      email: "sam@example.com",
      message: "Nice project, a question about the model.",
    });
  });

  it("clears the form after a successful send", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));
    const user = userEvent.setup();
    const { container } = render(<ContactForm />);
    await fillIn(container)(user);
    now = 20_000;

    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(screen.getByLabelText("Message")).toHaveValue(""));
  });

  it("refuses a submission that arrives faster than a person could type it", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContactForm />);
    await fillIn(container)(user);

    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("That was quick");
  });

  it("does not send when the hidden field has been filled in, but looks like it worked", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContactForm />);
    await fillIn(container)(user);
    now = 20_000;
    const trap = container.querySelector('input[name="website"]') as HTMLInputElement;
    await user.type(trap, "https://spam.example");

    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("your message was sent");
  });

  it("tells the visitor when the service rejects the message", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 500 }));
    const user = userEvent.setup();
    const { container } = render(<ContactForm />);
    await fillIn(container)(user);
    now = 20_000;

    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("didn't send"));
  });

  it("tells the visitor when the network fails", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const user = userEvent.setup();
    const { container } = render(<ContactForm />);
    await fillIn(container)(user);
    now = 20_000;

    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("didn't send"));
  });

  it("keeps the trap field out of the tab order and away from screen readers", () => {
    const { container } = render(<ContactForm />);

    const trap = container.querySelector('input[name="website"]') as HTMLInputElement;

    expect(trap.tabIndex).toBe(-1);
    expect(trap.closest('[aria-hidden="true"]')).not.toBeNull();
  });

  it("asks for the details it needs and limits their size", () => {
    render(<ContactForm />);

    expect(screen.getByLabelText("Your email")).toHaveAttribute("type", "email");
    expect(screen.getByLabelText("Name")).toBeRequired();
    expect(screen.getByLabelText("Message")).toHaveAttribute("minlength", "10");
    expect(screen.getByLabelText("Message")).toHaveAttribute("maxlength", "3000");
  });

  it("says where the details go", () => {
    render(<ContactForm />);

    expect(screen.getByText(/used only to reply/)).toBeInTheDocument();
  });
});
