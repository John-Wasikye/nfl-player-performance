// Details about who made the site. Change them here and every credit on the site updates.
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
