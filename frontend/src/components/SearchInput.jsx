export default function SearchInput({
  value,
  onChange,
  onSubmit,
  disabled,
}) {
  function handleKeyDown(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className="search-row">
      <input
        className="search-input"
        type="text"
        placeholder="Search for a jailbreak mechanic, framing move, or pattern."
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        aria-label="Search jailbreak prompt corpus"
      />

      <button className="search-button" type="button" onClick={onSubmit} disabled={disabled}>
        Search
      </button>
    </div>
  );
}
