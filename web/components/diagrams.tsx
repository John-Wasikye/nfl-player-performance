// Diagrams for the methodology pages.
//
// All of them draw with the theme tokens rather than fixed colours, so they read correctly in dark
// mode without a second copy. Each one carries a <title> and a short <desc>, because a diagram that
// only works visually leaves out anyone using a screen reader, and these carry real explanation
// rather than decoration.

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
  sub?: string;
  tone?: "plain" | "accent" | "good" | "bad";
}) {
  const fill = tone === "accent" ? ACCENT_SOFT : SURFACE2;
  const stroke = tone === "good" ? UP : tone === "bad" ? DOWN : tone === "accent" ? ACCENT : LINE;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={10} fill={fill} stroke={stroke} strokeWidth={1.5} />
      <text
        x={x + w / 2}
        y={sub ? y + h / 2 - 4 : y + h / 2 + 4}
        textAnchor="middle"
        fontSize={13}
        fontWeight={600}
        fill={FG}
      >
        {title}
      </text>
      {sub && (
        <text x={x + w / 2} y={y + h / 2 + 14} textAnchor="middle" fontSize={11} fill={MUTED}>
          {sub}
        </text>
      )}
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

function Defs() {
  return (
    <defs>
      <marker id="arrowhead" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">
        <polygon points="0 0, 9 3.5, 0 7" fill={MUTED} />
      </marker>
    </defs>
  );
}

/** What happens each week, in order, and where the lock sits. */
export function WeeklyCycleDiagram() {
  return (
    <Figure caption="The lock is the important step. Once projections are written down they are never changed, so the Report card measures forecasting rather than hindsight.">
      <svg viewBox="0 0 860 190" className="block h-auto w-full" role="img" aria-labelledby="cycle-t cycle-d">
        <title id="cycle-t">The weekly prediction cycle</title>
        <desc id="cycle-d">
          Five steps in a loop: the model makes projections, they are locked before the first
          kickoff, the games are played, every projection is graded against what happened, and the
          results are published on the Report card, which feeds back into the next week.
        </desc>
        <Defs />
        <Box x={10} y={40} title="Project" sub="every eligible player" tone="accent" />
        <Arrow x1={165} y1={67} x2={195} y2={67} />
        <Box x={200} y={40} title="Lock" sub="before first kickoff" tone="accent" />
        <Arrow x1={355} y1={67} x2={385} y2={67} />
        <Box x={390} y={40} title="Games happen" sub="nothing can change" />
        <Arrow x1={545} y1={67} x2={575} y2={67} />
        <Box x={580} y={40} title="Grade" sub="against the real score" />
        <Arrow x1={735} y1={67} x2={765} y2={67} />
        <Box x={700} y={125} w={150} h={44} title="Report card" tone="good" />
        <path
          d="M 775 94 L 775 125"
          stroke={MUTED}
          strokeWidth={1.5}
          fill="none"
          markerEnd="url(#arrowhead)"
        />
        <path
          d="M 700 147 L 85 147 L 85 100"
          stroke={MUTED}
          strokeWidth={1.5}
          strokeDasharray="4 3"
          fill="none"
          markerEnd="url(#arrowhead)"
        />
        <text x={390} y={164} fontSize={11} fill={MUTED}>
          what we learn feeds the next week
        </text>
      </svg>
    </Figure>
  );
}

/** The three populations, which are deliberately different. */
export function PopulationDiagram() {
  return (
    <Figure caption="Three different groups doing three different jobs. Each split was measured, not assumed.">
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
          Learning from them still helps, so we do.
        </text>
      </svg>
    </Figure>
  );
}

/** How one projection is built. */
export function ModelDiagram() {
  return (
    <Figure caption="Two simple models are averaged. The research found nothing more elaborate was justified: the limit is the sport's randomness, not the algorithm.">
      <svg viewBox="0 0 860 260" className="block h-auto w-full" role="img" aria-labelledby="model-t model-d">
        <title id="model-t">How one projection is built</title>
        <desc id="model-d">
          A player&apos;s recent form, usage, opponent and game context feed two models, a linear one
          and a tree-based one. Their average becomes the projection. Two further models produce the
          low and high ends of the range, which is then widened until it is honest. Separately, the
          injury report decides the chance the player takes the field.
        </desc>
        <Defs />
        <Box x={10} y={20} w={150} h={70} title="What we know" sub="form, usage, opponent," />
        <text x={85} y={78} textAnchor="middle" fontSize={11} fill={MUTED}>
          weather, betting line
        </text>
        <Arrow x1={165} y1={40} x2={215} y2={40} />
        <Arrow x1={165} y1={70} x2={215} y2={70} />
        <Arrow x1={165} y1={100} x2={215} y2={140} />
        <Box x={220} y={16} w={150} title="Linear model" sub="steady, simple" />
        <Box x={220} y={82} w={150} title="Tree model" sub="finds interactions" />
        <Arrow x1={375} y1={43} x2={425} y2={60} />
        <Arrow x1={375} y1={109} x2={425} y2={75} />
        <Box x={430} y={40} w={150} title="Average of both" sub="the projection" tone="accent" />
        <Arrow x1={585} y1={67} x2={635} y2={67} />
        <Box x={640} y={40} w={200} h={54} title="24.3 points" sub="the number you see" tone="good" />

        <Box x={220} y={150} w={150} title="Range models" sub="low end and high end" />
        <Arrow x1={375} y1={177} x2={425} y2={177} />
        <Box x={430} y={150} w={150} title="Widen until honest" sub="checked on unseen weeks" />
        <Arrow x1={585} y1={177} x2={635} y2={177} />
        <Box x={640} y={150} w={200} h={54} title="10.7 to 34.0" sub="the 80% range" tone="good" />

        <Box x={10} y={200} w={150} h={44} title="Injury report" sub="chance of playing" tone="bad" />
        <path
          d="M 165 222 L 700 222 L 700 208"
          stroke={MUTED}
          strokeWidth={1.5}
          strokeDasharray="4 3"
          fill="none"
          markerEnd="url(#arrowhead)"
        />
      </svg>
    </Figure>
  );
}

/** Why a single number would be dishonest. */
export function RangeDiagram() {
  return (
    <Figure caption="The same projection, shown two ways. The range is what the model actually believes; the single number is only its middle.">
      <svg viewBox="0 0 860 170" className="block h-auto w-full" role="img" aria-labelledby="range-t range-d">
        <title id="range-t">Why every projection carries a range</title>
        <desc id="range-d">
          A single number of 24.3 points looks precise. The honest 80% range for the same player runs
          from about 11 to 34 points, meaning four times out of five the real score lands somewhere
          in that band.
        </desc>
        <Defs />
        <text x={20} y={32} fontSize={13} fontWeight={600} fill={FG}>
          What a single number implies
        </text>
        <line x1={20} y1={58} x2={820} y2={58} stroke={LINE} strokeWidth={2} />
        <circle cx={430} cy={58} r={7} fill={ACCENT} />
        <text x={430} y={82} textAnchor="middle" fontSize={12} fill={MUTED}>
          &ldquo;24.3 points&rdquo;
        </text>

        <text x={20} y={112} fontSize={13} fontWeight={600} fill={FG}>
          What the model actually believes
        </text>
        <line x1={20} y1={138} x2={820} y2={138} stroke={LINE} strokeWidth={2} />
        <rect x={215} y={129} width={430} height={18} rx={9} fill={ACCENT_SOFT} stroke={ACCENT} />
        <circle cx={430} cy={138} r={7} fill={ACCENT} />
        <text x={215} y={162} textAnchor="middle" fontSize={12} fill={MUTED}>
          10.7
        </text>
        <text x={645} y={162} textAnchor="middle" fontSize={12} fill={MUTED}>
          34.0
        </text>
        <text x={430} y={162} textAnchor="middle" fontSize={12} fill={FG}>
          4 games out of 5 land in here
        </text>
      </svg>
    </Figure>
  );
}

/** The promotion gate: why accuracy can only ratchet forward. */
export function LearningLoopDiagram() {
  return (
    <Figure caption="A change is only adopted if it beats the current model on weeks neither of them was trained on. A tie keeps the incumbent, so published accuracy can hold steady but not slip.">
      <svg viewBox="0 0 860 250" className="block h-auto w-full" role="img" aria-labelledby="learn-t learn-d">
        <title id="learn-t">How the system improves over time</title>
        <desc id="learn-d">
          The failures of the current model are summarised. One new idea is written as code. It is
          replayed against five past seasons alongside the current model. If it is clearly better it
          replaces it; if not it is recorded as a dead end. Either way the result is published.
        </desc>
        <Defs />
        <Box x={10} y={30} title="Where it missed" sub="last week, summarised" />
        <Arrow x1={165} y1={57} x2={205} y2={57} />
        <Box x={210} y={30} title="One new idea" sub="written as real code" tone="accent" />
        <Arrow x1={365} y1={57} x2={405} y2={57} />
        <Box x={410} y={30} w={170} title="Replay 5 seasons" sub="old model vs new" />
        <Arrow x1={585} y1={57} x2={625} y2={57} />
        <Box x={630} y={22} w={210} h={70} title="Is it clearly better?" sub="and are its ranges honest?" />

        <path
          d="M 735 92 L 735 125"
          stroke={MUTED}
          strokeWidth={1.5}
          fill="none"
          markerEnd="url(#arrowhead)"
        />
        <text x={748} y={112} fontSize={11} fill={UP}>
          yes
        </text>
        <Box x={630} y={125} w={210} h={48} title="It replaces the model" tone="good" />

        <path
          d="M 630 57 L 600 57"
          stroke={MUTED}
          strokeWidth={0}
          fill="none"
        />
        <path
          d="M 660 92 L 400 92 L 400 150"
          stroke={MUTED}
          strokeWidth={1.5}
          strokeDasharray="4 3"
          fill="none"
          markerEnd="url(#arrowhead)"
        />
        <text x={470} y={86} fontSize={11} fill={DOWN}>
          no
        </text>
        <Box x={325} y={150} w={210} h={48} title="Recorded as a dead end" tone="bad" />
        <path
          d="M 430 198 L 430 220 L 735 220 L 735 175"
          stroke={MUTED}
          strokeWidth={1.5}
          strokeDasharray="4 3"
          fill="none"
        />
        <text x={520} y={236} fontSize={11} fill={MUTED}>
          both outcomes are published on the Report card
        </text>
      </svg>
    </Figure>
  );
}

/** How the composite ranking score is assembled. */
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

/** What the model can and cannot reach. */
export function CeilingDiagram() {
  return (
    <Figure caption="Measured, not guessed: even a model that knew each player's true season-long average in advance would only be about 7% better than ours. Most of a single game is genuinely unpredictable.">
      <svg viewBox="0 0 860 150" className="block h-auto w-full" role="img" aria-labelledby="ceiling-t ceiling-d">
        <title id="ceiling-t">How much room for improvement exists</title>
        <desc id="ceiling-d">
          A simple recent average is off by about 5.4 fantasy points a game. Our model is off by
          about 5.27. A perfect knower of each player&apos;s true average would still be off by about
          5.07. The gap between our model and that limit is under seven percent.
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
