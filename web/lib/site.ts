// Details about the site and who made it. Change them here and every mention updates.
export const SITE = {
  name: "Player Performance and Predictions",
  // The header has little room, so it shows this instead on narrow screens.
  shortName: "Player Performance",
};

export const AUTHOR = {
  name: "John Wasikye",
  initials: "JW",
  github: "https://github.com/John-Wasikye",
  repo: "https://github.com/John-Wasikye/nfl-player-performance",
  // Set this to the address of the site that lists your other projects, once it is live.
  projectsSite: "",
};

/** Where "my other projects" points: the projects site if it is set, otherwise GitHub. */
export function otherProjectsUrl(): string {
  return /^https?:\/\//.test(AUTHOR.projectsSite) ? AUTHOR.projectsSite : AUTHOR.github;
}

/** Links to other sites should open safely in a new tab; a "#" placeholder should not. */
export function linkProps(url: string) {
  return /^https?:\/\//.test(url)
    ? { href: url, target: "_blank", rel: "noopener noreferrer" }
    : { href: url };
}
