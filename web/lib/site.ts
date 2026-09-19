// Details about the site and who made it. Change them here and every mention updates.
export const SITE = {
  name: "Player Performance and Predictions",
  // The header has little room, so it shows this instead on narrow screens.
  shortName: "Player Performance",
};

export const AUTHOR = {
  name: "John Wasikye",
  initials: "JW",
  // TODO: replace "#" with the address of the portfolio site that lists your other projects.
  portfolioUrl: "#",
};

/** Links to other sites should open safely in a new tab; a "#" placeholder should not. */
export function linkProps(url: string) {
  return /^https?:\/\//.test(url)
    ? { href: url, target: "_blank", rel: "noopener noreferrer" }
    : { href: url };
}
