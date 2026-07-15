export default function Header() {
  return (
    <header className="site-header">
      <div className="wordmark">
        <span className="wordmark-dot" aria-hidden="true" />
        <span>RedLib</span>
      </div>

      <a
        className="header-link"
        href="https://github.com/nipun-ag/redlib"
        target="_blank"
        rel="noreferrer"
      >
        GitHub
      </a>
    </header>
  );
}
