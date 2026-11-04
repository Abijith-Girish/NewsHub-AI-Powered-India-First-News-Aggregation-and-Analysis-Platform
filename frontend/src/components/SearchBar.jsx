import { Search } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function SearchBar({ initialValue = '', onSubmit, placeholder, autoFocus = false }) {
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    setValue(initialValue);
  }, [initialValue]);

  function submit(event) {
    event.preventDefault();
    onSubmit(value.trim());
  }

  return (
    <form onSubmit={submit} className="relative" role="search">
      <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-400" aria-hidden />
      <input
        type="search"
        value={value}
        autoFocus={autoFocus}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholder || 'Search for AI, technology, politics, business…'}
        aria-label="Search any news topic"
        className="w-full rounded-2xl border border-ink-200 bg-white py-3.5 pl-12 pr-28 text-sm text-ink-900 shadow-card placeholder:text-ink-400 focus:border-ink-400 focus:outline-none focus:ring-2 focus:ring-ink-900/10 dark:border-ink-700 dark:bg-ink-900 dark:text-white dark:placeholder:text-ink-500"
      />
      <button type="submit" className="btn-primary absolute right-2 top-1/2 -translate-y-1/2 py-2 text-xs">
        Search
      </button>
    </form>
  );
}
