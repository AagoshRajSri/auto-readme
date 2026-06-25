import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Copy, CheckCircle2, AlertCircle, Download,
  GitBranch, Sparkles, ShieldCheck, FileText
} from 'lucide-react';
import './App.css';

const EXAMPLE_REPOS = ['fastapi', 'requests', 'flask'];
const EXAMPLE_URLS = [
  'https://github.com/tiangolo/fastapi',
  'https://github.com/psf/requests',
  'https://github.com/pallets/flask',
];

// Simple GitHub icon as SVG
const GithubIcon = ({ size = 20, ...props }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
  </svg>
);

const STEPS = [
  '→ Downloading repository archive',
  '→ Walking AST and extracting symbols',
  '→ Building section prompts',
  '→ Calling Gemini 1.5 Flash',
  '→ Running hallucination guard',
];

export default function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState('preview');
  const resultRef = useRef(null);
  const stepTimerRef = useRef(null);

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setLoadingStep(0);
    setError(null);
    setResult(null);
    setCopied(false);

    // Animate through steps while request runs
    let step = 0;
    stepTimerRef.current = setInterval(() => {
      step = Math.min(step + 1, STEPS.length - 1);
      setLoadingStep(step);
    }, 1800);

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/generate';
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ github_url: url }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Generation failed');
      setResult(data);
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    } catch (err) {
      setError(err.message);
    } finally {
      clearInterval(stepTimerRef.current);
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(result.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleDownload = () => {
    const blob = new Blob([result.markdown], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'README.md';
    a.click();
  };

  return (
    <div className="app">
      {/* ── NAV ── */}
      <nav className="nav">
        <span className="nav-logo">auto-readme</span>
        <a
          href="https://github.com/AagoshRajSri/auto-readme"
          target="_blank"
          rel="noreferrer"
          className="nav-link"
          id="nav-github-link"
        >
          <GithubIcon size={16} />
          GitHub
        </a>
      </nav>

      <main className="main">
        {/* ── HERO ── */}
        <section className="hero">
          {/* Blueprint markers */}
          <div className="blueprint-marker bm-tl" />
          <div className="blueprint-marker bm-tr" />
          <div className="blueprint-marker bm-bl" />
          <div className="blueprint-marker bm-br" />
          <div className="corner-bracket cb-tl" />
          <div className="corner-bracket cb-tr" />

          <h1 className="hero-headline">
            Beautiful READMEs,<br />Architected.
          </h1>
          <p className="hero-sub">
            Intelligent documentation generation from your code's blueprint.
          </p>

          {/* Repo Card */}
          <form onSubmit={handleGenerate} id="generate-form">
            <div className="repo-card">
              {loading ? (
                /* ── Inline loading state ── */
                <div className="card-loading">
                  <div className="card-loading-grid">
                    {Array.from({ length: 10 }).map((_, i) => (
                      <div key={i} className="loading-cell" style={{ animationDelay: `${i * 0.1}s` }} />
                    ))}
                  </div>
                  <div className="card-loading-steps">
                    {STEPS.map((step, i) => (
                      <div key={i} className={`loading-step ${i < loadingStep ? 'done' : ''} ${i === loadingStep ? 'active' : ''}`}>
                        {step}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  <div className="drop-zone">
                    <div className="drop-icon">
                      <GithubIcon size={32} />
                    </div>
                    <p className="drop-text">Drop your repository link here to analyze and generate</p>
                  </div>

                  <div className="input-group">
                    <input
                      id="repo-url-input"
                      type="text"
                      className="repo-input"
                      placeholder="https://github.com/username/repository"
                      value={url}
                      onChange={e => setUrl(e.target.value)}
                      disabled={loading}
                    />
                    <button
                      id="generate-btn"
                      type="submit"
                      className="generate-btn"
                      disabled={loading || !url.trim()}
                    >
                      Generate Documentation
                    </button>
                  </div>

                  {/* Examples */}
                  <div className="examples">
                    <span className="examples-label">try:</span>
                    {EXAMPLE_REPOS.map((name, i) => (
                      <button
                        key={name}
                        type="button"
                        className="example-chip"
                        onClick={() => setUrl(EXAMPLE_URLS[i])}
                      >
                        {name}
                      </button>
                    ))}
                  </div>

                  {error && (
                    <div className="error-bar" id="error-message">
                      <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
                      {error}
                    </div>
                  )}
                </>
              )}
            </div>
          </form>
        </section>

        {/* ── LOADING ── */}
        {loading && <LoadingState />}

        {/* ── RESULT ── */}
        {result && (
          <section className="result-section" ref={resultRef} id="result-section">
            <div className="result-header">
              <div className="result-title">
                <FileText size={14} />
                {result.repo_name} / README.md
              </div>
              <div className="result-actions">
                <button id="copy-btn" className="action-btn" onClick={handleCopy}>
                  {copied
                    ? <><CheckCircle2 size={13} /> Copied</>
                    : <><Copy size={13} /> Copy MD</>
                  }
                </button>
                <button id="download-btn" className="action-btn action-btn-primary" onClick={handleDownload}>
                  <Download size={13} /> Download
                </button>
              </div>
            </div>

            <div className="tab-bar">
              <button
                className={`tab ${activeTab === 'preview' ? 'tab-active' : ''}`}
                onClick={() => setActiveTab('preview')}
              >Preview</button>
              <button
                className={`tab ${activeTab === 'raw' ? 'tab-active' : ''}`}
                onClick={() => setActiveTab('raw')}
              >Raw Markdown</button>
            </div>

            <div className="result-window">
              {activeTab === 'preview' ? (
                <article className="markdown-body">
                  <ReactMarkdown>{result.markdown}</ReactMarkdown>
                </article>
              ) : (
                <pre className="raw-body">{result.markdown}</pre>
              )}
            </div>
          </section>
        )}

        {/* ── HOW IT WORKS ── */}
        <section className="how-section" id="how-it-works">
          <div className="how-header">
            <h2 className="how-title">How it works</h2>
            <div className="how-rule" />
            <span className="how-step">v1.0 // PIPELINE</span>
          </div>

          <div className="how-grid">
            <div className="how-card">
              <div className="how-card-icon">
                <GitBranch size={24} strokeWidth={1.5} />
              </div>
              <div className="how-card-num">01 / ANALYSIS</div>
              <h3 className="how-card-title">AST Analysis &amp; Blueprinting</h3>
              <p className="how-card-desc">
                Reads real function signatures, docstrings, and class structures
                directly from your Python source tree. Zero guessing.
              </p>
            </div>

            <div className="how-card">
              <div className="how-card-icon">
                <Sparkles size={24} strokeWidth={1.5} />
              </div>
              <div className="how-card-num">02 / GENERATION</div>
              <h3 className="how-card-title">Gemini 2.5 Flash Engine</h3>
              <p className="how-card-desc">
                Google's fastest reasoning model drafts polished, developer-grade
                prose grounded in the extracted blueprint data.
              </p>
            </div>

            <div className="how-card">
              <div className="how-card-icon">
                <ShieldCheck size={24} strokeWidth={1.5} />
              </div>
              <div className="how-card-num">03 / VALIDATION</div>
              <h3 className="how-card-title">Hallucination Guard &amp; Validation</h3>
              <p className="how-card-desc">
                Every symbol in the generated output is cross-referenced against
                the codebase before a single line is written.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* ── FOOTER ── */}
      <footer className="footer">
        <span>Built with auto-readme · Open source on</span>
        <a href="https://github.com/AagoshRajSri/auto-readme" target="_blank" rel="noreferrer">
          GitHub
        </a>
      </footer>
    </div>
  );
}
