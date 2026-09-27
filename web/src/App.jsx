import React, { Suspense, lazy, useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  ArrowRight,
  ShieldCheck,
  Link2,
  ScanLine,
  Eye,
  Check,
  X,
  Pause,
  Play,
  ChevronDown,
  AlertTriangle,
  LoaderCircle,
  Github,
  RefreshCw,
} from "lucide-react";

const Visuals = lazy(() => import("./Visuals"));
const LiquidMark = lazy(() => import("./LiquidMark"));

class VisualBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="shield-fallback">
        <ShieldCheck size={180} />
      </div>
    ) : (
      this.props.children
    );
  }
}
const faqs = [
  [
    "Does PhishGuard open the link?",
    "No. The model reads the URL string without visiting the destination. Your submitted URL is sent to this local prediction service for analysis. This preview does not save scan history.",
  ],
  [
    "What does the score mean?",
    "The model estimates a phishing score from URL patterns. It is not calibrated to real-world risk. A low score is not a guarantee that a website is safe.",
  ],
  [
    "Can I trust every prediction?",
    "Use it as a second opinion. On the internal test set, the model missed 11.53% of labeled phishing URLs and flagged 11.96% of labeled benign URLs. New campaigns and noisy labels remain limitations.",
  ],
];

export default function App() {
  const [motion, setMotion] = useState(
    () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [graphics, setGraphics] = useState(false);
  const [url, setUrl] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [service, setService] = useState("checking");
  const [openFaq, setOpenFaq] = useState(0);
  const input = useRef();
  const request = useRef(null);
  useEffect(() => {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2");
    setGraphics(!!gl);
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = (event) => setMotion(!event.matches);
    media.addEventListener("change", onChange);
    const controller = new AbortController();
    fetch("/model/health", { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then((data) => setService(data.restart_required ? "restart" : "online"))
      .catch(() => setService("offline"));
    return () => {
      controller.abort();
      request.current?.abort();
      media.removeEventListener("change", onChange);
    };
  }, []);
  function focusScanner() {
    document
      .getElementById("scanner")
      .scrollIntoView({
        behavior: motion ? "smooth" : "auto",
        block: "center",
      });
    input.current?.focus({ preventScroll: true });
  }
  async function scan(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    const value = url.trim();
    try {
      const parsed = new URL(
        /^[a-z][a-z\d+.-]*:\/\//i.test(value) ? value : "https://" + value,
      );
      if (
        !["http:", "https:"].includes(parsed.protocol) ||
        !parsed.hostname ||
        !value ||
        /\s/.test(value)
      )
        throw new Error();
    } catch {
      setError("Enter a web address, such as https://example.com.");
      return;
    }
    setBusy(true);
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("/model/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: value }),
        signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok)
        throw new Error(
          response.status === 422
            ? "This URL could not be read. Check the address and try again."
            : "The scanner is unavailable. Try again when the prediction service is running.",
        );
      if (
        !["legitimate", "phishing"].includes(data.label) ||
        !Number.isFinite(data.phishing_probability)
      )
        throw new Error(
          "The scanner returned an unexpected response. Please try again.",
        );
      setResult(data);
      setService("online");
    } catch (err) {
      setError(
        err.name === "AbortError"
          ? "The scan timed out. Please try again."
          : err instanceof SyntaxError
            ? "The scanner is offline. Start the prediction service and try again."
            : err.message || "Unable to reach the scanner. Please try again.",
      );
    } finally {
      clearTimeout(timeout);
      setBusy(false);
    }
  }
  return (
    <div className="site">
      <a className="skip-link" href="#scanner">
        Skip to URL scanner
      </a>
      <header className="nav shell">
        <a href="#top" className="brand" aria-label="PhishGuard home">
          <span className="brand-symbol">
            {graphics ? (
              <Suspense fallback={<ShieldCheck />}>
                <VisualBoundary>
                  <LiquidMark motion={motion} />
                </VisualBoundary>
              </Suspense>
            ) : (
              <ShieldCheck />
            )}
          </span>
          phishguard<span className="brand-dot">.</span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#research">The research</a>
          <a href="#questions">Questions</a>
        </nav>
        <a
          className="nav-source"
          href="https://github.com/Girijesh94/PhishGuard"
          target="_blank"
          rel="noreferrer"
        >
          <Github size={16} />
          <span>Open source</span>
          <ArrowUpRight size={15} />
        </a>
      </header>
      <main id="top">
        <section className="hero shell">
          <div className="hero-copy">
            <div className="research-tag">
              <span /> A little doubt. A smarter click.
            </div>
            <h1>
              Some links aren't
              <br />
              what they seem.
            </h1>
            <p className="hero-description">
              Look beneath the surface. Screen suspicious URLs for signs of
              phishing—before you decide to open them.
            </p>
            <div className="hero-actions">
              <button className="primary" onClick={focusScanner}>
                Check a link <ArrowUpRight size={19} />
              </button>
              <a className="text-link" href="#how-it-works">
                See how it works <ArrowRight size={17} />
              </a>
            </div>
            <div className="hero-assurance">
              <span>
                <Check size={14} /> No destination visit
              </span>
              <span>
                <Check size={14} /> No account needed
              </span>
            </div>
          </div>
          <div className="hero-art">
            <div className="orbital-label">
              <span /> URL intelligence
            </div>
            <VisualBoundary>
              {graphics ? (
                <Suspense
                  fallback={
                    <div className="shield-fallback">
                      <ShieldCheck size={180} />
                    </div>
                  }
                >
                  <Visuals motion={motion} />
                </Suspense>
              ) : (
                <div className="shield-fallback">
                  <ShieldCheck size={180} />
                </div>
              )}
            </VisualBoundary>
            <div className="art-caption">
              <span>Patterns, brought into focus.</span>
              <button
                aria-label={
                  motion ? "Pause visual motion" : "Resume visual motion"
                }
                aria-pressed={!motion}
                onClick={() => setMotion(!motion)}
              >
                {motion ? <Pause size={14} /> : <Play size={14} />}
              </button>
            </div>
          </div>
        </section>

        <section
          className="scanner-section shell"
          id="scanner"
          aria-labelledby="scanner-heading"
        >
          <div className="scanner-top">
            <div>
              <span className="section-kicker">
                A second opinion for your next click
              </span>
              <h2 id="scanner-heading">Where does that link lead?</h2>
            </div>
            <span className={"service-state " + service}>
              <i />
              {service === "online"
                ? "Model connected"
                : service === "checking"
                  ? "Connecting to model"
                  : service === "restart"
                    ? "Model restart needed"
                    : "Model offline"}
            </span>
          </div>
          <form onSubmit={scan} className="scan-form">
            <label htmlFor="url">
              <Link2 size={22} />
              <span className="sr-only">URL to check</span>
            </label>
            <input
              id="url"
              ref={input}
              value={url}
              maxLength={65536}
              onChange={(e) => {
                setUrl(e.target.value);
                setResult(null);
                setError("");
              }}
              placeholder="Paste a link you're unsure about…"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck="false"
              disabled={busy}
              aria-describedby="scan-note"
            />
            <button
              type="submit"
              className="primary"
              disabled={busy || !url.trim()}
            >
              {busy ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <ScanLine size={18} />
              )}{" "}
              {busy ? "Checking…" : "Analyze link"}
            </button>
          </form>
          <div className="scan-foot">
            <p id="scan-note">
              <ShieldCheck size={14} /> The destination is never opened. Your
              URL is sent to the local model.
            </p>
            <button
              className="example"
              disabled={busy}
              onClick={() => {
                setUrl("https://www.google.com");
                setResult(null);
                setError("");
                input.current?.focus();
              }}
            >
              Try an example <ArrowRight size={13} />
            </button>
          </div>
          {error && (
            <div className="scan-error" role="alert">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {result && (
            <div className={"scan-result " + result.label} role="status">
              <div className="result-summary">
                <span className="result-icon">
                  {result.label === "phishing" ? (
                    <AlertTriangle />
                  ) : (
                    <ShieldCheck />
                  )}
                </span>
                <div>
                  <h3>
                    {result.label === "phishing"
                      ? "This link looks suspicious"
                      : "Fewer signs of phishing"}
                  </h3>
                  <p>
                    {result.label === "phishing"
                      ? "Avoid entering passwords or personal details. Verify the sender independently."
                      : "The model leans legitimate. Still verify the sender and website before sharing information."}
                  </p>
                </div>
                <div className="score">
                  <strong>
                    {(result.phishing_probability * 100).toFixed(1)}%
                  </strong>
                  <span>Phishing score</span>
                </div>
              </div>
              <details>
                <summary>What influenced the text model?</summary>
                <div className="feature-list">
                  {result.top_features?.map((f, i) => (
                    <span key={i}>
                      <code>{f.feature.replace(/^text:/, "")}</code>{" "}
                      {f.contribution > 0 ? "+" : ""}
                      {f.contribution.toFixed(3)}
                    </span>
                  ))}
                </div>
                <p>{result.top_features_method}</p>
              </details>
              <p className="result-note">
                An uncalibrated model score, not a safety guarantee. This
                preview does not save scans.
              </p>
            </div>
          )}
        </section>

        <section className="how-section shell" id="how-it-works">
          <div className="section-intro">
            <span className="section-kicker">
              Small pause. Better decisions.
            </span>
            <h2>
              Curiosity is good.
              <br />
              Blind trust isn't.
            </h2>
            <p>
              Messages move fast. Take a moment to understand the link behind
              the promise.
            </p>
          </div>
          <div className="steps">
            <article>
              <span className="step-icon">
                <Link2 />
              </span>
              <div>
                <span className="step-number">01 / Bring the link</span>
                <h3>Paste, don't open.</h3>
                <p>
                  Copy a URL from a message, email, or QR code. Let the
                  destination wait.
                </p>
              </div>
            </article>
            <article>
              <span className="step-icon">
                <ScanLine />
              </span>
              <div>
                <span className="step-number">02 / Read the patterns</span>
                <h3>Look a little closer.</h3>
                <p>
                  Character patterns and URL structure give two different views
                  of the same link.
                </p>
              </div>
            </article>
            <article>
              <span className="step-icon">
                <Eye />
              </span>
              <div>
                <span className="step-number">03 / Make the call</span>
                <h3>Keep your judgment.</h3>
                <p>
                  Use the model's result as another signal. When in doubt,
                  verify through a trusted channel.
                </p>
              </div>
            </article>
          </div>
        </section>

        <section className="research-section shell" id="research">
          <div className="research-heading">
            <div>
              <span className="section-kicker">Built in the open</span>
              <h2>
                A model with
                <br />
                its limits on the table.
              </h2>
            </div>
            <p>
              Measured on 70,494 URLs in a fixed internal test set. Related
              domains stay in the same data partition. These results don't
              promise real-world safety.
            </p>
          </div>
          <div className="metrics">
            <div>
              <span>Phishing recall</span>
              <strong>
                88.47<small>%</small>
              </strong>
              <p>Labeled phishing URLs caught</p>
            </div>
            <div>
              <span>Phishing precision</span>
              <strong>
                86.71<small>%</small>
              </strong>
              <p>Flagged URLs labeled phishing</p>
            </div>
            <div>
              <span>False-positive rate</span>
              <strong>
                11.96<small>%</small>
              </strong>
              <p>Benign URLs incorrectly flagged</p>
            </div>
            <a
              href="https://github.com/Girijesh94/PhishGuard/blob/main/metrics.md"
              target="_blank"
              rel="noreferrer"
            >
              <span>See the whole picture</span>
              <ArrowUpRight size={30} />
              <p>
                Methods, mistakes,
                <br />
                and what comes next.
              </p>
            </a>
          </div>
        </section>

        <section className="faq-section shell" id="questions">
          <div>
            <span className="section-kicker">Before you trust the result</span>
            <h2>A few honest answers.</h2>
          </div>
          <div className="faq-list">
            {faqs.map(([q, a], i) => (
              <div className="faq" key={q}>
                <h3>
                  <button
                    aria-expanded={openFaq === i}
                    aria-controls={"answer-" + i}
                    onClick={() => setOpenFaq(openFaq === i ? -1 : i)}
                  >
                    {q}
                    <ChevronDown
                      className={openFaq === i ? "rotated" : ""}
                      size={18}
                    />
                  </button>
                </h3>
                <p id={"answer-" + i} hidden={openFaq !== i}>
                  {a}
                </p>
              </div>
            ))}
          </div>
        </section>
        <section className="bottom-cta shell">
          <ShieldCheck size={36} />
          <h2>
            A moment of caution
            <br />
            can change the story.
          </h2>
          <button className="primary" onClick={focusScanner}>
            Check a link <ArrowUpRight size={18} />
          </button>
        </section>
      </main>
      <footer className="shell">
        <a href="#top" className="brand">
          <ShieldCheck size={20} /> phishguard.
        </a>
        <p>A research project for more thoughtful clicks.</p>
        <a
          href="https://github.com/Girijesh94/PhishGuard"
          target="_blank"
          rel="noreferrer"
        >
          View source <ArrowUpRight size={14} />
        </a>
      </footer>
    </div>
  );
}
