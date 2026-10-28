import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowDown,
  ArrowDownUp,
  ArrowUp,
  BarChart3,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Download,
  FileUp,
  HeartPulse,
  Map,
  Search,
  UsersRound,
  Waves,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = ["#168d87", "#48b4a7", "#87c9b9", "#f0aa68", "#e78676", "#6576bc"];
const API = import.meta.env.VITE_API_BASE_URL || "/api";
const number = (value, digits = 1) =>
  Number(value || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });

function queryString(filters, extra = {}) {
  const params = new URLSearchParams();
  if (filters.year) params.set("year", filters.year);
  if (filters.state) params.set("state", filters.state);
  if (filters.search.trim()) params.set("search", filters.search.trim());
  Object.entries(extra).forEach(([key, value]) => params.set(key, value));
  return params.toString();
}

async function request(path) {
  const response = await fetch(`${API}${path}`);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `Request failed (${response.status}).`);
  }
  return body;
}

function SectionTitle({ eyebrow, title, detail, action }) {
  return (
    <div className="section-title">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h2>{title}</h2>
        {detail && <p>{detail}</p>}
      </div>
      {action}
    </div>
  );
}

function ChartCard({ title, subtitle, children, className = "" }) {
  return (
    <section className={`chart-card ${className}`}>
      <div className="chart-heading">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

function ChartEmpty() {
  return <div className="chart-empty">No records match these filters.</div>;
}

function FloodcastMark({ size = 21 }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M3 8.25c2.25 0 2.25-2 4.5-2s2.25 2 4.5 2 2.25-2 4.5-2 2.25 2 4.5 2"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M3 14c2.25 0 2.25-2 4.5-2s2.25 2 4.5 2 2.25-2 4.5-2 2.25 2 4.5 2"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M5 18.5h14"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        opacity=".65"
      />
    </svg>
  );
}

function CustomTooltip({ active, payload, label, valueName }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      {label && <strong>{label}</strong>}
      {payload.map((item, index) => (
        <span key={`${item.name}-${index}`} style={{ color: item.color || item.fill }}>
          {item.name || valueName}: {number(item.value, 2)}
        </span>
      ))}
    </div>
  );
}

function CorrelationGrid({ labels, values }) {
  if (!labels?.length || !values?.length) return <ChartEmpty />;
  return (
    <div className="correlation-grid-wrap">
      <div className="correlation-grid">
        <div className="correlation-corner" />
        {labels.map((label) => (
          <div className="correlation-top-label" key={label} title={label}>
            {label}
          </div>
        ))}
        {labels.map((label, row) => (
          <div className="correlation-row" key={label}>
            <div className="correlation-side-label">{label}</div>
            {values[row].map((value, column) => {
              const strength = value == null ? 0 : Math.abs(value);
              const background =
                value == null
                  ? "#f1f4f4"
                  : value >= 0
                    ? `rgba(22, 141, 135, ${0.08 + strength * 0.65})`
                    : `rgba(218, 112, 93, ${0.08 + strength * 0.65})`;
              return (
                <div
                  key={`${row}-${column}`}
                  className="correlation-cell"
                  style={{ background }}
                  title={`${label} × ${labels[column]}: ${value == null ? "not available" : value}`}
                >
                  {value == null ? "—" : value.toFixed(2)}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [filters, setFilters] = useState({ year: "", state: "", search: "" });
  const [filterOptions, setFilterOptions] = useState({ years: [], states: [], source: "" });
  const [summary, setSummary] = useState(null);
  const [charts, setCharts] = useState(null);
  const [records, setRecords] = useState({ records: [], total: 0, pages: 0, page: 1 });
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState({ column: "Year", order: "asc" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState("");
  const [datasetVersion, setDatasetVersion] = useState(0);
  const fileInput = useRef(null);

  const getFilters = useCallback(async () => {
    const data = await request("/filters");
    setFilterOptions(data);
  }, []);

  useEffect(() => {
    getFilters().catch((loadError) => setError(loadError.message));
  }, [getFilters, datasetVersion]);

  useEffect(() => {
    setPage(1);
  }, [filters.year, filters.state, filters.search]);

  const currentQuery = useMemo(() => queryString(filters), [filters]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      request(`/summary?${currentQuery}`),
      request(`/charts?${currentQuery}`),
      request(
        `/records?${queryString(filters, {
          page,
          page_size: 10,
          sort_by: sort.column,
          sort_order: sort.order,
        })}`,
      ),
    ])
      .then(([nextSummary, nextCharts, nextRecords]) => {
        if (!active) return;
        setSummary(nextSummary);
        setCharts(nextCharts);
        setRecords(nextRecords);
      })
      .catch((loadError) => {
        if (active) setError(loadError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [currentQuery, filters, page, sort, datasetVersion]);

  const updateFilter = (key, value) =>
    setFilters((current) => ({ ...current, [key]: value }));

  const handleSort = (column) => {
    setSort((current) => ({
      column,
      order: current.column === column && current.order === "asc" ? "desc" : "asc",
    }));
    setPage(1);
  };

  const exportCsv = async () => {
    try {
      const response = await fetch(`${API}/records/export?${currentQuery}`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Could not export the filtered records.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "flood-impact-records.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (exportError) {
      setError(exportError.message);
    }
  };

  const uploadCsv = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    setUploading(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${API}/upload`, { method: "POST", body: formData });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "CSV upload failed.");
      setFilters({ year: "", state: "", search: "" });
      setPage(1);
      setNotice(
        `Loaded ${number(body.records, 0)} validated records across ${body.states} States/UTs.`,
      );
      setDatasetVersion((value) => value + 1);
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setUploading(false);
    }
  };

  const isEmpty = !loading && summary?.records === 0;
  const scatterYears = [...new Set((charts?.house_damage_vs_population || []).map((point) => point.year))].sort();
  const tableColumns = [
    ["Year", "Year"],
    ["Name of State/UT", "State / UT"],
    ["Area Affected (Mha)", "Area affected (Mha)"],
    ["Population Affected (Million)", "Population affected (M)"],
    ["Human Lives Lost Nos.", "Lives lost"],
    ["Damages to Crops - Value (Rs. Crore)", "Crop damage (Rs. cr)"],
    ["Damage to Houses - Value (Rs. Crore)", "House damage (Rs. cr)"],
    ["Total Damages Crops,Houses & Public Utilities (Rs. Crore)", "Total damage (Rs. cr)"],
  ];

  return (
    <div className="app-shell">
      <header className="topbar" id="top">
        <a className="brand" href="#overview" aria-label="Floodcast dashboard home">
          <span className="brand-mark"><FloodcastMark /></span>
          <span>Floodcast</span>
        </a>
        <nav className="topnav" aria-label="Main navigation">
          <a href="#overview">Overview</a>
          <a href="#analysis">Analysis</a>
          <a href="#records">Records</a>
        </nav>
        <div className="topbar-right">
          <span className="dataset-badge"><span /> Historical dataset</span>
          <button className="button button-outline upload-button" onClick={() => fileInput.current?.click()} disabled={uploading}>
            <FileUp size={16} />
            {uploading ? "Validating…" : "Upload CSV"}
          </button>
          <input ref={fileInput} className="visually-hidden" type="file" accept=".csv,text/csv" onChange={uploadCsv} />
        </div>
      </header>

      <main className="main-content">
        <section className="hero">
          <div className="hero-copy">
            <div className="hero-kicker"><span className="live-dot" /> INDIA · FLOOD IMPACT ARCHIVE</div>
            <h1>Understanding the<br /><em>impact of floods.</em></h1>
            <p>Explore reported flood impacts across India’s States and Union Territories, from people affected to damage recorded.</p>
            <div className="historical-note"><CircleAlert size={16} /> Historical impact analysis only — this dashboard does not forecast or predict floods.</div>
          </div>
          <div className="hero-graphic" aria-hidden="true">
            <div className="graphic-orbit orbit-one" />
            <div className="graphic-orbit orbit-two" />
            <div className="graphic-core"><Waves size={56} strokeWidth={1.3} /></div>
            <span className="graphic-label label-one">2016 — 2018</span>
            <span className="graphic-label label-two">35 STATES & UTs</span>
            <span className="graphic-point point-one" />
            <span className="graphic-point point-two" />
          </div>
        </section>

        <section className="filter-bar" aria-label="Dashboard filters">
          <div className="filter-intro"><span className="filter-icon"><Map size={17} /></span><div><strong>Explore the data</strong><small>Refine your view</small></div></div>
          <label className="select-wrap">
            <span>Year</span>
            <select value={filters.year} onChange={(event) => updateFilter("year", event.target.value)}>
              <option value="">All years</option>
              {filterOptions.years.map((year) => <option value={year} key={year}>{year}</option>)}
            </select><ChevronDown size={15} />
          </label>
          <label className="select-wrap state-select">
            <span>State / UT</span>
            <select value={filters.state} onChange={(event) => updateFilter("state", event.target.value)}>
              <option value="">All States & UTs</option>
              {filterOptions.states.map((state) => <option value={state} key={state}>{state}</option>)}
            </select><ChevronDown size={15} />
          </label>
          <label className="search-wrap">
            <Search size={16} />
            <input value={filters.search} onChange={(event) => updateFilter("search", event.target.value)} placeholder="Search a State or UT…" aria-label="Search a State or UT" />
            {filters.search && <button aria-label="Clear search" onClick={() => updateFilter("search", "")}>×</button>}
          </label>
          <div className="filter-caption">{filterOptions.records ? `${number(filterOptions.records, 0)} records` : "Loading dataset…"}</div>
        </section>

        {error && <div className="alert alert-error" role="alert"><CircleAlert size={18} /><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error">×</button></div>}
        {notice && <div className="alert alert-success" role="status"><Activity size={18} /><span>{notice}</span><button onClick={() => setNotice("")} aria-label="Dismiss message">×</button></div>}

        {loading && !summary ? (
          <div className="loading-panel"><span className="spinner" /> Loading flood impact data…</div>
        ) : isEmpty ? (
          <div className="empty-panel"><Search size={28} /><h2>No records found</h2><p>Try changing your filters or search term.</p><button className="button button-teal" onClick={() => setFilters({ year: "", state: "", search: "" })}>Clear filters</button></div>
        ) : (
          <>
            <section className="overview-section" id="overview">
              <SectionTitle eyebrow="THE BIG PICTURE" title="Impact at a glance" detail="Reported totals across your selected view." />
              <div className="metric-grid">
                <article className="metric-card metric-population"><div className="metric-top"><span className="metric-icon"><UsersRound size={18} /></span><span className="metric-unit">MILLION PEOPLE</span></div><div className="metric-value">{loading ? "—" : number(summary?.population_affected_million, 2)}<span className="metric-suffix">M</span></div><div className="metric-label">Population affected</div><div className="metric-foot"><span className="metric-dot" /> People reported affected</div></article>
                <article className="metric-card metric-lives"><div className="metric-top"><span className="metric-icon"><HeartPulse size={18} /></span><span className="metric-unit">PEOPLE</span></div><div className="metric-value">{loading ? "—" : number(summary?.lives_lost, 0)}</div><div className="metric-label">Human lives lost</div><div className="metric-foot"><span className="metric-dot" /> Reported fatalities</div></article>
                <article className="metric-card metric-area"><div className="metric-top"><span className="metric-icon"><Waves size={18} /></span><span className="metric-unit">MILLION HECTARES</span></div><div className="metric-value">{loading ? "—" : number(summary?.area_affected_mha, 3)}<span className="metric-suffix">Mha</span></div><div className="metric-label">Area affected</div><div className="metric-foot"><span className="metric-dot" /> Reported affected area</div></article>
                <article className="metric-card metric-damage"><div className="metric-top"><span className="metric-icon"><BarChart3 size={18} /></span><span className="metric-unit">RS. CRORE</span></div><div className="metric-value">{loading ? "—" : number(summary?.total_damage_crore, 2)}</div><div className="metric-label">Total reported damage</div><div className="metric-foot"><span className="metric-dot" /> Crops, houses & utilities</div></article>
              </div>
            </section>

            <section className="analysis-section" id="analysis">
              <SectionTitle eyebrow="EXPLORE THE PATTERNS" title="Flood impact, by the numbers" detail="Interactive views based on the cleaned state-year records." />
              <div className="chart-grid">
                <ChartCard title="Lives lost by State / UT" subtitle="Top 10 states and remaining states combined">
                  {charts?.lives_lost_by_state?.length ? <div className="chart-body pie-layout"><ResponsiveContainer width="53%" height={256}><PieChart><Pie data={charts.lives_lost_by_state} dataKey="value" nameKey="name" innerRadius={66} outerRadius={103} paddingAngle={2} strokeWidth={2} stroke="#fff">{charts.lives_lost_by_state.map((entry, index) => <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />)}</Pie><Tooltip content={<CustomTooltip />} /></PieChart></ResponsiveContainer><div className="pie-legend">{charts.lives_lost_by_state.map((entry, index) => <div key={entry.name}><span style={{ background: COLORS[index % COLORS.length] }} /> <span className="legend-name">{entry.name}</span><strong>{number(entry.value, 0)}</strong></div>)}</div></div> : <ChartEmpty />}
                </ChartCard>

                <ChartCard title="Area affected distribution" subtitle="Number of state-year records by affected area (Mha)">
                  {charts?.area_distribution?.length ? <div className="chart-body"><ResponsiveContainer width="100%" height={280}><BarChart data={charts.area_distribution} margin={{ top: 10, right: 12, bottom: 38, left: -12 }}><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e9eeee" /><XAxis dataKey="range" angle={-43} textAnchor="end" interval={2} tick={{ fontSize: 10, fill: "#82908f" }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#82908f" }} axisLine={false} tickLine={false} /><Tooltip content={<CustomTooltip valueName="Records" />} /><Bar dataKey="count" name="Records" fill="#45aa9c" radius={[4, 4, 0, 0]} maxBarSize={24} /></BarChart></ResponsiveContainer></div> : <ChartEmpty />}
                </ChartCard>

                <ChartCard title="Population affected by year" subtitle="Total reported population affected (million)">
                  {charts?.population_by_year?.length ? <div className="chart-body"><ResponsiveContainer width="100%" height={280}><LineChart data={charts.population_by_year} margin={{ top: 16, right: 18, bottom: 8, left: 0 }}><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e9eeee" /><XAxis dataKey="year" tick={{ fontSize: 12, fill: "#82908f" }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 11, fill: "#82908f" }} axisLine={false} tickLine={false} /><Tooltip content={<CustomTooltip valueName="Million people" />} /><Line type="monotone" dataKey="population" name="Population (M)" stroke="#168d87" strokeWidth={3} dot={{ r: 5, fill: "#168d87", stroke: "white", strokeWidth: 2 }} activeDot={{ r: 7 }} /></LineChart></ResponsiveContainer></div> : <ChartEmpty />}
                </ChartCard>

                <ChartCard title="Top States / UTs by crop damage" subtitle="Reported crop damage value (Rs. crore)">
                  {charts?.crop_damage_by_state?.length ? <div className="chart-body"><ResponsiveContainer width="100%" height={280}><BarChart data={charts.crop_damage_by_state} layout="vertical" margin={{ top: 4, right: 18, bottom: 4, left: 8 }}><CartesianGrid strokeDasharray="3 5" horizontal={false} stroke="#e9eeee" /><XAxis type="number" tick={{ fontSize: 11, fill: "#82908f" }} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="state" width={112} tick={{ fontSize: 10, fill: "#65716f" }} axisLine={false} tickLine={false} /><Tooltip content={<CustomTooltip valueName="Rs. crore" />} /><Bar dataKey="crop_damage" name="Crop damage" fill="#eea568" radius={[0, 4, 4, 0]} maxBarSize={16} /></BarChart></ResponsiveContainer></div> : <ChartEmpty />}
                </ChartCard>

                <ChartCard title="House damage vs population affected" subtitle="Each point represents one State / UT and year">
                  {charts?.house_damage_vs_population?.length ? <div className="chart-body"><ResponsiveContainer width="100%" height={280}><ScatterChart margin={{ top: 12, right: 18, bottom: 10, left: 2 }}><CartesianGrid strokeDasharray="3 5" stroke="#e9eeee" /><XAxis type="number" dataKey="house_damage" name="House damage" unit=" cr" tick={{ fontSize: 10, fill: "#82908f" }} axisLine={false} tickLine={false} label={{ value: "House damage (Rs. crore)", position: "insideBottom", offset: -3, fill: "#879492", fontSize: 10 }} /><YAxis type="number" dataKey="population" name="Population affected" unit=" M" tick={{ fontSize: 10, fill: "#82908f" }} axisLine={false} tickLine={false} label={{ value: "Population (M)", angle: -90, position: "insideLeft", fill: "#879492", fontSize: 10 }} /><Tooltip cursor={{ strokeDasharray: "3 3" }} content={({ active, payload }) => active && payload?.length ? <div className="chart-tooltip"><strong>{payload[0].payload.state} · {payload[0].payload.year}</strong><span>House damage: Rs. {number(payload[0].payload.house_damage, 2)} crore</span><span>Population: {number(payload[0].payload.population, 3)} million</span></div> : null} /><Legend verticalAlign="top" height={28} iconType="circle" wrapperStyle={{ fontSize: 11 }} />{scatterYears.map((year, index) => <Scatter key={year} name={String(year)} data={charts.house_damage_vs_population.filter((point) => point.year === year)} fill={COLORS[index % COLORS.length]} />)}</ScatterChart></ResponsiveContainer></div> : <ChartEmpty />}
                </ChartCard>

                <ChartCard title="Impact variable correlations" subtitle="Pearson correlation across the selected records">
                  <CorrelationGrid labels={charts?.correlation_labels} values={charts?.correlations} />
                  <div className="correlation-foot"><span><i className="corr-positive" /> Positive</span><span><i className="corr-negative" /> Negative</span><span>−1 to +1</span></div>
                </ChartCard>
              </div>
            </section>

            <section className="records-section" id="records">
              <div className="table-heading">
                <div><span className="eyebrow">THE SOURCE RECORDS</span><h2>State-year detail</h2><p>{number(records.total, 0)} records in this view</p></div>
                <button className="button button-outline export-button" onClick={exportCsv} disabled={!records.total}><Download size={16} /> Export filtered CSV</button>
              </div>
              <div className="table-scroll">
                <table>
                  <thead><tr>{tableColumns.map(([column, label]) => <th key={column}><button className="sort-button" onClick={() => handleSort(column)}>{label}{sort.column === column ? (sort.order === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ArrowDownUp size={12} />}</button></th>)}</tr></thead>
                  <tbody>
                    {records.records.map((record, index) => <tr key={`${record.Year}-${record["Name of State/UT"]}-${index}`}>{tableColumns.map(([column]) => <td key={column} className={column === "Name of State/UT" ? "state-cell" : ""}>{column === "Year" ? record[column] : column === "Name of State/UT" ? record[column] : number(record[column], column.includes("Area") ? 3 : 2)}</td>)}</tr>)}
                    {!records.records.length && <tr><td colSpan={tableColumns.length} className="table-empty">No records match these filters.</td></tr>}
                  </tbody>
                </table>
              </div>
              <div className="table-footer"><span>Showing {records.total ? (page - 1) * 10 + 1 : 0}–{Math.min(page * 10, records.total)} of {number(records.total, 0)}</span><div className="pagination"><button aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}><ChevronLeft size={17} /></button><span>Page {page} of {Math.max(records.pages, 1)}</span><button aria-label="Next page" disabled={page >= records.pages} onClick={() => setPage((value) => Math.min(records.pages, value + 1))}><ChevronRight size={17} /></button></div></div>
            </section>
          </>
        )}
      </main>

      <footer className="footer"><div className="footer-brand"><span className="brand-mark"><FloodcastMark size={17} /></span><strong>Floodcast</strong></div><p>Historical flood impact data · India · 2016–2018</p><p className="footer-note">For analysis and awareness. Not a forecasting tool.</p></footer>
    </div>
  );
}
