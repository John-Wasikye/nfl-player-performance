// Diagrams for the methodology pages. Colours come from the theme tokens so they work in dark mode.

const FG = "var(--fg)";
const MUTED = "var(--muted)";
const LINE = "var(--line)";
const SURFACE2 = "var(--surface-2)";
const ACCENT = "var(--accent)";
const ACCENT_SOFT = "var(--accent-soft)";
const UP = "var(--up)";
const DOWN = "var(--down)";
const WARN = "var(--warn)";

function Figure({
  caption,
  children,
}: {
  caption: string;
  children: React.ReactNode;
}) {
  return (
    <figure className="my-6 max-w-full">
      <div className="w-full max-w-full overflow-x-auto rounded-2xl border border-line bg-surface p-4">
        <div className="min-w-[680px]">{children}</div>
      </div>
      <figcaption className="mt-2 text-sm text-muted">{caption}</figcaption>
    </figure>
  );
}

function Box({
  x,
  y,
  w = 150,
  h = 54,
  title,
  sub,
  tone = "plain",
}: {
  x: number;
  y: number;
  w?: number;
  h?: number;
  title: string;
  sub?: string | string[];
  tone?: "plain" | "accent" | "good" | "bad";
}) {
  const fill = tone === "accent" ? ACCENT_SOFT : SURFACE2;
  const stroke = tone === "good" ? UP : tone === "bad" ? DOWN : tone === "accent" ? ACCENT : LINE;
  const subs = sub === undefined ? [] : Array.isArray(sub) ? sub : [sub];
  const first = y + h / 2 - ((subs.length * 17) / 2) + 4;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={10} fill={fill} stroke={stroke} strokeWidth={1.5} />
      <text x={x + w / 2} y={first} textAnchor="middle" fontSize={13} fontWeight={600} fill={FG}>
        {title}
      </text>
      {subs.map((line, i) => (
        <text
          key={line}
          x={x + w / 2}
          y={first + 17 * (i + 1)}
          textAnchor="middle"
          fontSize={11}
          fill={MUTED}
        >
          {line}
        </text>
      ))}
    </g>
  );
}

function Arrow({
  x1,
  y1,
  x2,
  y2,
  label,
  dashed,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  label?: string;
  dashed?: boolean;
}) {
  return (
    <g>
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke={MUTED}
        strokeWidth={1.5}
        strokeDasharray={dashed ? "4 3" : undefined}
        markerEnd="url(#arrowhead)"
      />
      {label && (
        <text
          x={(x1 + x2) / 2}
          y={y1 === y2 ? y1 - 7 : (y1 + y2) / 2 - 6}
          textAnchor="middle"
          fontSize={11}
          fill={MUTED}
        >
          {label}
        </text>
      )}
    </g>
  );
}

function Elbow({ d, dashed }: { d: string; dashed?: boolean }) {
  return (
    <path
      d={d}
      fill="none"
      stroke={MUTED}
      strokeWidth={1.5}
      strokeDasharray={dashed ? "4 3" : undefined}
      markerEnd="url(#arrowhead)"
    />
  );
}

function Defs() {
  return (
    <defs>
      <marker id="arrowhead" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">
        <polygon points="0 0, 9 3.5, 0 7" fill={MUTED} />
      </marker>
    </defs>
  );
}

export function WeeklyCycleDiagram() {
  return (
    <Figure caption="Once projections are locked they are never changed, so the Report card measures forecasts, not hindsight.">
      <svg viewBox="0 0 860 200" className="block h-auto w-full" role="img" aria-labelledby="cycle-t cycle-d">
        <title id="cycle-t">The weekly prediction cycle</title>
        <desc id="cycle-d">
          Four steps in a row, then a loop back. The model makes projections, they are locked before
          the first kickoff, the games are played, and every projection is graded against what
          happened. The results go on the Report card, and what I learn feeds the next week.
        </desc>
        <Defs />
        <Box x={10} y={30} title="Project" sub="every eligible player" tone="accent" />
        <Arrow x1={165} y1={57} x2={195} y2={57} />
        <Box x={200} y={30} title="Lock" sub="before first kickoff" tone="accent" />
        <Arrow x1={355} y1={57} x2={385} y2={57} />
        <Box x={390} y={30} title="Games happen" sub="nothing can change" />
        <Arrow x1={545} y1={57} x2={575} y2={57} />
        <Box x={580} y={30} title="Grade" sub="against the real score" />

        <Arrow x1={655} y1={87} x2={655} y2={125} />
        <Box x={580} y={130} w={150} h={44} title="Report card" tone="good" />

        <Elbow d="M 580 152 L 85 152 L 85 92" dashed />
        <text x={330} y={172} textAnchor="middle" fontSize={11} fill={MUTED}>
          what I learn feeds the next week
        </text>
      </svg>
    </Figure>
  );
}

export function PopulationDiagram() {
  return (
    <Figure caption="Three groups of players doing three different jobs. Each split was tested.">
      <svg viewBox="0 0 860 230" className="block h-auto w-full" role="img" aria-labelledby="pop-t pop-d">
        <title id="pop-t">Which players are used for what</title>
        <desc id="pop-d">
          The model learns from every player with at least three previous games. It sets the width of
          its ranges using only the players good enough to be published. And it publishes only
          players averaging at least four fantasy points over their last five games.
        </desc>
        <Defs />
        <rect x={20} y={30} width={380} height={170} rx={12} fill={SURFACE2} stroke={LINE} />
        <text x={210} y={55} textAnchor="middle" fontSize={13} fontWeight={600} fill={FG}>
          Learn from: everyone with 3+ games
        </text>
        <text x={210} y={73} textAnchor="middle" fontSize={11} fill={MUTED}>
          12,411 player-games
        </text>
        <rect x={60} y={90} width={300} height={95} rx={10} fill={ACCENT_SOFT} stroke={ACCENT} />
        <text x={210} y={115} textAnchor="middle" fontSize={13} fontWeight={600} fill={FG}>
          Show, and judge on: a real role
        </text>
        <text x={210} y={133} textAnchor="middle" fontSize={11} fill={MUTED}>
          4+ points over the last five games
        </text>
        <text x={210} y={150} textAnchor="middle" fontSize={11} fill={MUTED}>
          8,464 player-games
        </text>
        <text x={210} y={172} textAnchor="middle" fontSize={11} fill={MUTED}>
          range widths are set here too
        </text>

        <text x={440} y={55} fontSize={13} fontWeight={600} fill={FG}>
          Why not just use everyone?
        </text>
        <text x={440} y={78} fontSize={12} fill={MUTED}>
          Below that line the model was measurably
        </text>
        <text x={440} y={96} fontSize={12} fill={MUTED}>
          worse than a player&apos;s own recent average.
        </text>
        <text x={440} y={124} fontSize={12} fill={MUTED}>
          A deep-bench player who scores near zero
        </text>
        <text x={440} y={142} fontSize={12} fill={MUTED}>
          every week needs no projection, and adding
        </text>
        <text x={440} y={160} fontSize={12} fill={MUTED}>
          one only made the numbers noisier.
        </text>
        <text x={440} y={188} fontSize={12} fill={FG} fontWeight={600}>
          Learning from them still helps, so the model does.
        </text>
      </svg>
    </Figure>
  );
}

export function ModelDiagram() {
  return (
    <Figure caption="Two simple models, averaged. Nothing more elaborate helped in testing.">
      <svg viewBox="0 0 860 300" className="block h-auto w-full" role="img" aria-labelledby="model-t model-d">
        <title id="model-t">How one projection is built</title>
        <desc id="model-d">
          A player&apos;s recent form, usage, opponent and game context feed three models. A linear
          model and a tree model are averaged to give the projection. A pair of range models are
          widened to match how often they missed, which gives the 80% range. Separately, the injury
          report gives the chance the player takes the field.
        </desc>
        <Defs />
        <Box x={10} y={45} w={150} h={84} title="Inputs" sub={["form, usage, opponent,", "betting line, roof"]} />
        <line x1={160} y1={87} x2={190} y2={87} stroke={MUTED} strokeWidth={1.5} />
        <line x1={190} y1={47} x2={190} y2={187} stroke={MUTED} strokeWidth={1.5} />
        <Arrow x1={190} y1={47} x2={215} y2={47} />
        <Arrow x1={190} y1={117} x2={215} y2={117} />
        <Arrow x1={190} y1={187} x2={215} y2={187} />

        <Box x={220} y={20} w={150} title="Linear model" sub="steady, simple" />
        <Box x={220} y={90} w={150} title="Tree model" sub="finds interactions" />
        <Box x={220} y={160} w={150} title="Range models" sub="low end and high end" />

        <line x1={370} y1={47} x2={400} y2={47} stroke={MUTED} strokeWidth={1.5} />
        <line x1={370} y1={117} x2={400} y2={117} stroke={MUTED} strokeWidth={1.5} />
        <line x1={400} y1={47} x2={400} y2={117} stroke={MUTED} strokeWidth={1.5} />
        <Arrow x1={400} y1={82} x2={425} y2={82} />
        <Box x={430} y={55} w={150} title="Average of both" sub="the projection" tone="accent" />
        <Arrow x1={580} y1={82} x2={635} y2={82} />
        <Box x={640} y={55} w={200} title="24.3 points" sub="the number you see" tone="good" />

        <Arrow x1={370} y1={187} x2={425} y2={187} />
        <Box x={430} y={160} w={150} title="Widen the range" sub="checked on unseen weeks" />
        <Arrow x1={580} y1={187} x2={635} y2={187} />
        <Box x={640} y={160} w={200} title="10.7 to 34.0" sub="the 80% range" tone="good" />

        <Box x={10} y={230} w={150} title="Injury report" sub="practice status" tone="bad" />
        <Arrow x1={160} y1={257} x2={635} y2={257} label="separate model" />
        <Box x={640} y={230} w={200} title="Chance of playing" sub="Questionable players only" tone="good" />
      </svg>
    </Figure>
  );
}

export function RangeDiagram() {
  return (
    <Figure caption="The same projection shown two ways. The single number is the middle of the range.">
      <svg viewBox="0 0 860 195" className="block h-auto w-full" role="img" aria-labelledby="range-t range-d">
        <title id="range-t">Why every projection carries a range</title>
        <desc id="range-d">
          A single number of 24.3 points looks precise. The 80% range for the same player runs
          from about 11 to 34 points, meaning four times out of five the real score lands somewhere
          in that band.
        </desc>
        <Defs />
        <text x={20} y={32} fontSize={13} fontWeight={600} fill={FG}>
          What a single number implies
        </text>
        <line x1={20} y1={58} x2={820} y2={58} stroke={LINE} strokeWidth={2} />
        <circle cx={464} cy={58} r={7} fill={ACCENT} />
        <text x={464} y={82} textAnchor="middle" fontSize={12} fill={MUTED}>
          &ldquo;24.3 points&rdquo;
        </text>

        <text x={20} y={112} fontSize={13} fontWeight={600} fill={FG}>
          The model&apos;s range
        </text>
        <line x1={20} y1={138} x2={820} y2={138} stroke={LINE} strokeWidth={2} />
        <rect x={215} y={129} width={430} height={18} rx={9} fill={ACCENT_SOFT} stroke={ACCENT} />
        <circle cx={464} cy={138} r={7} fill={ACCENT} />
        <text x={215} y={168} textAnchor="middle" fontSize={12} fill={MUTED}>
          10.7
        </text>
        <text x={645} y={168} textAnchor="middle" fontSize={12} fill={MUTED}>
          34.0
        </text>
        <text x={430} y={182} textAnchor="middle" fontSize={12} fill={FG}>
          4 games out of 5 land in here
        </text>
      </svg>
    </Figure>
  );
}

export function LearningLoopDiagram() {
  return (
    <Figure caption="A change is adopted only if it beats the current model on weeks neither was trained on. A tie keeps the current model.">
      <svg viewBox="0 0 860 310" className="block h-auto w-full" role="img" aria-labelledby="learn-t learn-d">
        <title id="learn-t">How a change to the model is adopted</title>
        <desc id="learn-d">
          Where the current model missed is summarised. One new idea is written as code and replayed
          against five past seasons alongside the current model. A decision follows: if the change is
          clearly better and its ranges still hold, it replaces the model. If not, it is recorded as
          a dead end. Both outcomes go on the Report card.
        </desc>
        <Defs />
        <Box x={10} y={20} w={210} title="Where it missed" sub="last week, summarised" />
        <Arrow x1={225} y1={47} x2={315} y2={47} />
        <Box x={320} y={20} w={210} title="One new idea" sub="written as real code" tone="accent" />
        <Arrow x1={535} y1={47} x2={625} y2={47} />
        <Box x={630} y={20} w={210} title="Replay 5 seasons" sub="old model vs new" />

        <Arrow x1={735} y1={77} x2={735} y2={110} />
        <Box x={630} y={115} w={210} title="Clearly better?" sub="and do the ranges hold?" />

        <Elbow d="M 630 142 L 505 142 L 505 205" />
        <text x={570} y={134} textAnchor="middle" fontSize={12} fontWeight={600} fill={DOWN}>
          no
        </text>
        <Arrow x1={735} y1={175} x2={735} y2={205} />
        <text x={747} y={195} fontSize={12} fontWeight={600} fill={UP}>
          yes
        </text>

        <Box x={400} y={210} w={210} title="Recorded as a dead end" tone="bad" />
        <Box x={630} y={210} w={210} title="It replaces the model" tone="good" />

        <path d="M 400 280 L 400 286 L 840 286 L 840 280" fill="none" stroke={LINE} strokeWidth={1.5} />
        <text x={620} y={304} textAnchor="middle" fontSize={11} fill={MUTED}>
          both outcomes go on the Report card
        </text>
      </svg>
    </Figure>
  );
}

export function CompositeDiagram({ efficiency }: { efficiency: number }) {
  const production = 100 - efficiency;
  const splitX = 40 + (760 * efficiency) / 100;
  return (
    <Figure caption="Every measure is first turned into a 0-100 score against other players at the same position, so a quarterback is only ever compared with quarterbacks.">
      <svg viewBox="0 0 860 250" className="block h-auto w-full" role="img" aria-labelledby="comp-t comp-d">
        <title id="comp-t">How the composite score is built</title>
        <desc id="comp-d">
          Efficiency measures, which are rates per play, and production measures, which are totals,
          are each scored against other players at the same position, then blended into one score.
        </desc>
        <Defs />
        <Box x={10} y={20} w={200} h={64} title="Efficiency" sub="rates: per play, per target" tone="accent" />
        <Box x={10} y={110} w={200} h={64} title="Production" sub="totals: yards, touchdowns" />
        <Arrow x1={215} y1={52} x2={265} y2={52} />
        <Arrow x1={215} y1={142} x2={265} y2={142} />
        <Box x={270} y={20} w={210} h={64} title="Scored 0-100" sub="against the same position" />
        <Box x={270} y={110} w={210} h={64} title="Scored 0-100" sub="against the same position" />
        <Arrow x1={485} y1={52} x2={535} y2={85} />
        <Arrow x1={485} y1={142} x2={535} y2={110} />
        <Box x={540} y={70} w={300} h={64} title="Composite score" sub="one number per player" tone="good" />

        <text x={40} y={212} fontSize={12} fontWeight={600} fill={FG}>
          Current blend
        </text>
        <rect x={40} y={222} width={760} height={18} rx={9} fill={SURFACE2} stroke={LINE} />
        <rect x={40} y={222} width={(760 * efficiency) / 100} height={18} rx={9} fill={ACCENT} />
        <text x={splitX / 2 + 20} y={236} textAnchor="middle" fontSize={11} fill="var(--accent-fg)">
          {efficiency}% efficiency
        </text>
        <text x={(splitX + 800) / 2} y={236} textAnchor="middle" fontSize={11} fill={MUTED}>
          {production}% production
        </text>
      </svg>
    </Figure>
  );
}

export function CeilingDiagram() {
  return (
    <Figure caption="Even a model that knew each player's true season-long average in advance would only be about 7% better than mine. Most of a single game can't be predicted.">
      <svg viewBox="0 0 860 150" className="block h-auto w-full" role="img" aria-labelledby="ceiling-t ceiling-d">
        <title id="ceiling-t">How much room for improvement exists</title>
        <desc id="ceiling-d">
          A simple recent average is off by about 5.4 fantasy points a game. My model is off by
          about 5.27. A perfect knower of each player&apos;s true average would still be off by about
          5.07. The gap between my model and that limit is under seven percent.
        </desc>
        <Defs />
        {[
          { label: "A simple recent average", value: 5.44, y: 20, tone: SURFACE2, stroke: LINE },
          { label: "This model", value: 5.27, y: 60, tone: ACCENT_SOFT, stroke: ACCENT },
          { label: "Knowing the true average", value: 5.07, y: 100, tone: "var(--up-soft)", stroke: UP },
        ].map((row) => (
          <g key={row.label}>
            <text x={10} y={row.y + 20} fontSize={12} fill={FG}>
              {row.label}
            </text>
            <rect
              x={210}
              y={row.y + 4}
              width={row.value * 85}
              height={22}
              rx={6}
              fill={row.tone}
              stroke={row.stroke}
            />
            <text x={220 + row.value * 85} y={row.y + 20} fontSize={12} fill={MUTED}>
              off by {row.value.toFixed(2)} points
            </text>
          </g>
        ))}
        <text x={210} y={142} fontSize={11} fill={WARN}>
          Lower is better. The whole remaining gap between this model and perfect knowledge is 0.20
          points.
        </text>
      </svg>
    </Figure>
  );
}
