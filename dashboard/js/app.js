/* Painel REEE Brasil – lógica do dashboard (sem build; d3 + Chart.js via CDN). */
(() => {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const nf0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
  const nf3 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3, minimumFractionDigits: 3 });
  const fmt = (v, f = nf0) => (v === null || v === undefined || Number.isNaN(v) ? "–" : f.format(v));
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch { return false; } },
  };

  const IND = {
    pontos_100k: { label: "Pontos por 100 mil hab.", f: (v) => fmt(v, nf2) },
    pct_pop_coberta: { label: "% da população coberta", f: (v) => fmt(v, nf1) + " %" },
    pct_obrigados_com_ponto: { label: "% dos obrigados com ponto", f: (v) => fmt(v, nf1) + " %" },
    kg_hab: { label: "kg por habitante", f: (v) => fmt(v, nf3) },
    deficit_pontos: { label: "Pontos faltantes", f: (v) => fmt(v) },
  };

  let D, GEO, M; // pacote, geojson, municípios
  const S = { ano: null, uf: "", ind: "pontos_100k", city: null };
  const charts = {};

  /* ---------------- carga ---------------- */
  async function load() {
    const [d, g] = await Promise.all([
      fetch("data/dashboard.json").then((r) => r.json()),
      fetch("data/uf.geojson").then((r) => r.json()),
    ]);
    D = d; GEO = g; M = d.municipios;
    M.n = M.cod.length;
    M.idx = new Map(M.cod.map((c, i) => [c, i]));
    S.ano = d.meta.anos[d.meta.anos.length - 1];
    init();
  }

  const anoIdx = () => D.meta.anos.indexOf(S.ano);
  const ufRow = (uf, ano = S.ano) => D.uf_ano.find((r) => r.uf === uf && r.ano === ano);
  const brRow = (ano = S.ano) => D.brasil_ano.find((r) => r.ano === ano);
  const scopeRow = (ano = S.ano) => (S.uf ? ufRow(S.uf, ano) : brRow(ano));
  const ufNome = (uf) => (D.ufs.find((u) => u.uf === uf) || {}).nome_uf || uf;

  /* ---------------- init ---------------- */
  function init() {
    $("#banner").hidden = D.meta.fonte !== "demo";
    // anos
    $("#years").innerHTML = D.meta.anos.map((a) => `<button type="button" data-ano="${a}" aria-pressed="${a === S.ano}">${a}</button>`).join("");
    $("#years").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      S.ano = +b.dataset.ano; $$("#years button").forEach((x) => x.setAttribute("aria-pressed", x === b)); render();
    });
    // UF
    const sel = $("#f-uf");
    D.ufs.slice().sort((a, b) => a.nome_uf.localeCompare(b.nome_uf, "pt-BR"))
      .forEach((u) => sel.insertAdjacentHTML("beforeend", `<option value="${u.uf}">${u.nome_uf}</option>`));
    sel.addEventListener("change", () => { S.uf = sel.value; render(); });
    $("#f-ind").addEventListener("change", (e) => { S.ind = e.target.value; renderMap(); renderRank(); });
    // abas
    $$(".tab").forEach((t) => t.addEventListener("click", () => selectTab(t.id.replace("tab-", ""))));
    const hash = location.hash.replace("#", "");
    if (["gestor", "cidadao", "dados"].includes(hash)) selectTab(hash);
    // simulador
    $("#sim-n").addEventListener("input", (e) => { $("#sim-n-lbl").textContent = e.target.value; renderPrio(); });
    // cidadão
    const dl = $("#lista-mun");
    dl.innerHTML = M.nome.map((n, i) => `<option value="${n} – ${M.uf[i]}"></option>`).join("");
    $("#busca").addEventListener("change", onBusca);
    $("#busca").addEventListener("keydown", (e) => { if (e.key === "Enter") onBusca(); });
    S.city = store.get("reee_city", null);
    if (S.city === null || M.cod[S.city] === undefined) {
      // começa pela capital mais populosa
      let best = 0; for (let i = 0; i < M.n; i++) if (M.capital[i] && M.pop[i] > M.pop[best]) best = i;
      S.city = best;
    }
    initParticipacao();
    initAvaliacao();
    renderDados();
    render();
    const mq = matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener?.("change", () => render());
    new MutationObserver(() => render()).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(renderMap, 150); });
  }

  function selectTab(id) {
    $$(".tab").forEach((t) => t.setAttribute("aria-selected", t.id === "tab-" + id));
    $$(".panel").forEach((p) => (p.hidden = p.id !== "panel-" + id));
    $("#filters").hidden = id === "dados";
    if (id === "cidadao") renderCidade();
  }

  function render() {
    renderKPIs(); renderMap(); renderRank(); renderCharts(); renderEntidades(); renderPrio(); renderCidade();
  }

  /* ---------------- KPIs ---------------- */
  function delta(cur, prev) {
    if (!prev) return "";
    const d = ((cur - prev) / prev) * 100;
    const cls = d >= 0 ? "up" : "down";
    return `<span class="delta ${cls} mono">${d >= 0 ? "▲" : "▼"} ${fmt(Math.abs(d), nf1)} %</span> vs ${S.ano - 1}`;
  }
  function renderKPIs() {
    const r = scopeRow(), p = scopeRow(S.ano - 1);
    const lugar = S.uf ? ufNome(S.uf) : "Brasil";
    $("#k-pontos").innerHTML = `<span class="label">Pontos ativos · ${lugar}</span>
      <div><span class="value">${fmt(r.pontos)}</span></div>
      <div class="sub">${delta(r.pontos, p && p.pontos)}</div>
      <div class="sub">${fmt(r.pontos_100k, nf2)} por 100 mil habitantes</div>`;
    const fonteMassa = r.fonte_massa === "uf" ? " · dado só por UF" : "";
    $("#k-massa").innerHTML = `<span class="label">REEE recebido · ${S.ano}</span>
      <div><span class="value">${fmt(r.toneladas)}</span><span class="unit">t</span></div>
      <div class="sub">${delta(r.toneladas, p && p.toneladas)}</div>
      <div class="sub">${fmt(r.kg_hab, nf3)} kg/hab.${fonteMassa}</div>`;
    const meta = D.meta.metas_decreto[S.ano];
    let status;
    if (S.uf) {
      status = `<span class="pill">${fmt(r.pct_obrigados_com_ponto, nf1)} % dos obrigados da UF</span>`;
    } else if (!meta) {
      status = `<span class="pill"><i class="dot" style="background:var(--muted)"></i>Metas começam em 2021</span>`;
    } else {
      const ok = r.obrigados_com_ponto >= meta.municipios;
      status = `<span class="pill"><i class="dot" style="background:var(${ok ? "--good" : "--critical"})"></i>${ok ? "Meta atingida" : "Abaixo da meta"}: ${fmt(meta.municipios)} municípios</span>`;
    }
    $("#k-meta").innerHTML = `<span class="label">Municípios &gt; 80 mil hab. com ponto</span>
      <div><span class="value">${fmt(r.obrigados_com_ponto)}</span><span class="unit">de ${fmt(r.obrigados)}</span></div>
      ${status}`;
    $("#k-deficit").innerHTML = `<span class="label">Pontos faltantes (1 a cada 25 mil hab.)</span>
      <div><span class="value">${fmt(r.deficit_pontos)}</span></div>
      <div class="sub">${fmt(r.obrigados_cumprem)} de ${fmt(r.obrigados)} municípios obrigados cumprem a densidade mínima</div>`;
  }

  /* ---------------- mapa ---------------- */
  const tip = $("#tip");
  function showTip(e, html) { tip.innerHTML = html; tip.hidden = false; moveTip(e); }
  function moveTip(e) {
    const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
    const y = Math.min(e.clientY + 14, innerHeight - tip.offsetHeight - 8);
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  const hideTip = () => (tip.hidden = true);

  function statusMun(i, j) {
    const pop = M.pop[i], pts = M.pontos[i][j];
    const nec = pop > D.meta.limiar_populacional ? Math.ceil(pop / D.meta.hab_por_ponto_decreto) : 0;
    if (nec === 0) return pts > 0 ? { k: "livre", c: "--accent", t: "Tem ponto (sem obrigação legal)" } : { k: "nenhum", c: "--muted", t: "Sem ponto (sem obrigação legal)" };
    if (pts >= nec) return { k: "cumpre", c: "--good", t: "Cumpre a densidade mínima", nec };
    if (pts > 0) return { k: "parcial", c: "--warning", t: "Cobertura abaixo do mínimo", nec };
    return { k: "sem", c: "--critical", t: "Obrigado e sem ponto", nec };
  }

  function renderMap() {
    const box = $("#map");
    const W = Math.max(320, box.clientWidth || 640), H = Math.round(Math.min(W * 0.82, 640));
    const feats = GEO.features;
    const vals = new Map(D.uf_ano.filter((r) => r.ano === S.ano).map((r) => [r.uf, r[S.ind]]));
    const arr = [...vals.values()].filter((v) => v !== null && !Number.isNaN(v));
    const ramp = ["--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5"].map(css);
    const q = d3.scaleQuantile().domain(arr).range(ramp);
    const focus = S.uf ? feats.filter((f) => f.properties.uf === S.uf) : feats;
    const proj = d3.geoMercator().fitExtent([[8, 8], [W - 8, H - 8]], { type: "FeatureCollection", features: focus });
    const path = d3.geoPath(proj);

    box.innerHTML = "";
    const svg = d3.select(box).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img")
      .attr("aria-label", `Mapa do Brasil por ${IND[S.ind].label}, ${S.ano}`);
    svg.append("g").selectAll("path").data(feats).join("path")
      .attr("class", (f) => "uf-shape" + (S.uf && f.properties.uf !== S.uf ? " dim" : ""))
      .attr("d", path)
      .attr("fill", (f) => {
        if (S.uf && f.properties.uf === S.uf) return css("--surface-2"); // UF em foco: fundo neutro para ler os municípios
        const v = vals.get(f.properties.uf); return v === null || v === undefined ? css("--grid") : q(v);
      })
      .on("mousemove", (e, f) => {
        const r = ufRow(f.properties.uf);
        showTip(e, `<b>${f.properties.nome}</b><br>${IND[S.ind].label}: ${IND[S.ind].f(r[S.ind])}<br>${fmt(r.pontos)} pontos · ${fmt(r.toneladas)} t`);
      })
      .on("mouseleave", hideTip)
      .on("click", (e, f) => { const u = f.properties.uf; S.uf = S.uf === u ? "" : u; $("#f-uf").value = S.uf; hideTip(); render(); });

    // municípios
    const j = anoIdx(), pts = [];
    for (let i = 0; i < M.n; i++) {
      if (S.uf && M.uf[i] !== S.uf) continue;
      const st = statusMun(i, j);
      if (!S.uf && st.nec === undefined) continue;
      if (S.uf && st.k === "nenhum") continue;
      pts.push({ i, st, xy: proj([M.lon[i], M.lat[i]]) });
    }
    const rScale = d3.scaleSqrt().domain([0, d3.max(M.pop)]).range([S.uf ? 2.5 : 1.6, S.uf ? 16 : 10]);
    pts.sort((a, b) => M.pop[b.i] - M.pop[a.i]);
    svg.append("g").selectAll("circle").data(pts).join("circle")
      .attr("class", "mun-dot").attr("cx", (d) => d.xy[0]).attr("cy", (d) => d.xy[1])
      .attr("r", (d) => (d.st.nec === undefined ? 2.5 : Math.max(3, rScale(M.pop[d.i]))))
      .attr("fill", (d) => css(d.st.c))
      .on("mousemove", (e, d) => {
        const i = d.i;
        showTip(e, `<b>${M.nome[i]} – ${M.uf[i]}</b><br>${fmt(M.pop[i])} hab.<br>${fmt(M.pontos[i][j])} pontos${d.st.nec ? " de " + d.st.nec + " necessários" : ""}<br>${d.st.t}`);
      })
      .on("mouseleave", hideTip)
      .on("click", (e, d) => { S.city = d.i; store.set("reee_city", d.i); selectTab("cidadao"); hideTip(); });

    // legenda
    const qs = q.quantiles();
    const lim = [d3.min(arr), ...qs, d3.max(arr)];
    $("#map-title").textContent = `${IND[S.ind].label} · ${S.uf ? ufNome(S.uf) : "Brasil"} · ${S.ano}`;
    $("#map-legend").innerHTML = `
      <div><div class="swatches">${ramp.map((c) => `<i style="background:${c}"></i>`).join("")}</div>
      <div class="ticks"><span>${IND[S.ind].f(lim[0])}</span><span>${IND[S.ind].f(lim[lim.length - 1])}</span></div></div>
      <span><i class="dot" style="background:var(--good)"></i> Cumpre 1 ponto/25 mil hab.</span>
      <span><i class="dot" style="background:var(--warning)"></i> Tem ponto, com déficit</span>
      <span><i class="dot" style="background:var(--critical)"></i> Obrigado e sem ponto</span>
      ${S.uf ? `<span><i class="dot" style="background:var(--accent)"></i> Abaixo de 80 mil hab. com ponto</span>` : ""}`;
  }

  /* ---------------- ranking UF ---------------- */
  function renderRank() {
    const rows = D.uf_ano.filter((r) => r.ano === S.ano && r[S.ind] !== null).sort((a, b) => b[S.ind] - a[S.ind]);
    const max = d3.max(rows, (r) => r[S.ind]) || 1;
    $("#rank-sub").textContent = `${IND[S.ind].label}, ${S.ano}. Clique para filtrar.`;
    $("#rank").innerHTML = rows.map((r) => `
      <div class="bar-row${r.uf === S.uf ? " sel" : ""}" data-uf="${r.uf}" role="button" tabindex="0" aria-label="${ufNome(r.uf)}: ${IND[S.ind].f(r[S.ind])}">
        <span class="mono">${r.uf}</span>
        <span class="track"><span class="fill" style="width:${(r[S.ind] / max) * 100}%"></span></span>
        <span class="v">${IND[S.ind].f(r[S.ind])}</span>
      </div>`).join("");
    $$("#rank .bar-row").forEach((el) => {
      const go = () => { const u = el.dataset.uf; S.uf = S.uf === u ? "" : u; $("#f-uf").value = S.uf; render(); };
      el.addEventListener("click", go);
      el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
  }

  /* ---------------- gráficos ---------------- */
  function baseOpts(yTitle) {
    const ink = css("--ink-2"), grid = css("--grid"), muted = css("--muted");
    return {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: ink, boxWidth: 12, font: { family: css("--font-body") } } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmt(c.parsed.y)}` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: muted, font: { family: css("--font-mono") } }, border: { color: css("--axis") } },
        y: { beginAtZero: true, grid: { color: grid }, border: { display: false },
             ticks: { color: muted, font: { family: css("--font-mono") }, callback: (v) => fmt(v) },
             title: { display: !!yTitle, text: yTitle, color: muted } },
      },
    };
  }
  function mk(id, cfg) { charts[id]?.destroy(); charts[id] = new Chart($("#" + id), cfg); }

  function renderCharts() {
    const anos = D.meta.anos, rows = anos.map((a) => scopeRow(a));
    const s1 = css("--series-1"), s2 = css("--series-2"), surf = css("--surface");
    const sel = anos.indexOf(S.ano);
    const ptR = anos.map((_, i) => (i === sel ? 6 : 3));
    mk("c-pontos", { type: "line", data: { labels: anos, datasets: [{
      label: S.uf ? ufNome(S.uf) : "Brasil", data: rows.map((r) => r.pontos), borderColor: s1, backgroundColor: s1 + "22",
      fill: true, tension: 0.25, borderWidth: 2, pointRadius: ptR, pointBackgroundColor: s1, pointBorderColor: surf, pointBorderWidth: 2 }] },
      options: { ...baseOpts("pontos"), plugins: { ...baseOpts().plugins, legend: { display: false } } } });

    const meta = anos.map((a) => (S.uf ? null : D.meta.metas_decreto[a]?.municipios ?? null));
    const ds = [{ type: "bar", label: "Com ponto", data: rows.map((r) => r.obrigados_com_ponto), backgroundColor: s1, borderRadius: 4, maxBarThickness: 36 }];
    if (S.uf) ds.push({ type: "line", label: "Total de municípios obrigados", data: rows.map((r) => r.obrigados), borderColor: s2, borderDash: [5, 4], pointRadius: 0, borderWidth: 2 });
    else ds.push({ type: "line", label: "Meta acumulada do Decreto", data: meta, borderColor: s2, borderDash: [5, 4], pointRadius: 4, pointBackgroundColor: s2, pointBorderColor: surf, borderWidth: 2, spanGaps: false });
    mk("c-meta", { data: { labels: anos, datasets: ds }, options: baseOpts("municípios") });

    mk("c-massa", { type: "bar", data: { labels: anos, datasets: [{ label: "Toneladas", data: rows.map((r) => r.toneladas),
      backgroundColor: rows.map((r, i) => (i === sel ? s1 : s1 + "99")), borderRadius: 4, maxBarThickness: 36 }] },
      options: { ...baseOpts("t"), plugins: { ...baseOpts().plugins, legend: { display: false } } } });
    const soUF = rows.filter((r) => r.fonte_massa === "uf").map((r) => r.ano);
    $("#massa-sub").textContent = "Toneladas por ano" + (soUF.length ? ` · ${soUF.join(" e ")}: relatório só por UF` : "");
  }

  function hbars(el, rows, color) {
    const max = d3.max(rows, (r) => r.v) || 1;
    el.innerHTML = rows.map((r) => `<div class="bar-row" style="grid-template-columns:9.5rem minmax(0,1fr) 4.6rem;cursor:default">
      <span>${r.k}</span><span class="track"><span class="fill" style="width:${(r.v / max) * 100}%;background:${color}"></span></span>
      <span class="v">${fmt(r.v)}</span></div>`).join("");
  }
  function renderEntidades() {
    $("#ent-sub").textContent = `Brasil, ${S.ano}`;
    const e = D.entidade_ano.filter((r) => r.ano === S.ano).map((r) => ({ k: r.entidade, v: r.pontos })).sort((a, b) => b.v - a.v);
    const t = D.tipo_ano.filter((r) => r.ano === S.ano).map((r) => ({ k: r.tipo, v: r.pontos })).sort((a, b) => b.v - a.v);
    hbars($("#entidades"), e, css("--series-1"));
    hbars($("#tipos"), t, css("--series-3"));
  }

  /* ---------------- prioridade + simulador ---------------- */
  /* Regra do simulador: segue a ordem do índice de prioridade e instala, em cada
     município, o necessário para zerar o déficit (ou 1 ponto, se não for obrigado)
     antes de passar ao próximo. */
  function simular(cands, n) {
    let resto = n;
    return cands.map((c) => {
      const precisa = Math.max(1, c.deficit_pontos);
      const add = Math.min(precisa, resto);
      resto -= add;
      return { c, add };
    });
  }
  function renderPrio() {
    const anoP = D.meta.anos[D.meta.anos.length - 1];
    const cands = D.prioridade.filter((r) => !S.uf || r.uf === S.uf);
    const n = +$("#sim-n").value;
    const sim = simular(cands, n);
    const add = new Map(sim.map((a) => [a.c.cod_ibge, a.add]));
    const benef = sim.filter((a) => a.add > 0);
    const novosCumprem = benef.filter((a) => a.c.deficit_pontos > 0 && a.add >= a.c.deficit_pontos).length;
    const popNova = benef.filter((a) => a.c.pontos === 0).reduce((s, a) => s + a.c.populacao, 0);
    const defAntes = cands.reduce((s, c) => s + c.deficit_pontos, 0);
    const defDepois = sim.reduce((s, a) => s + Math.max(0, a.c.deficit_pontos - a.add), 0);
    $("#prio-sub").textContent = `${fmt(cands.length)} municípios candidatos em ${S.uf ? ufNome(S.uf) : "todo o Brasil"} (base ${anoP}). Arraste para simular a instalação de novos pontos.`;
    $("#sim-out").innerHTML = `
      <div><span class="label">Municípios atendidos</span><b>${fmt(benef.length)}</b></div>
      <div><span class="label">Passam a cumprir o Decreto</span><b>${fmt(novosCumprem)}</b></div>
      <div><span class="label">Pessoas com 1º ponto na cidade</span><b>${fmt(popNova)}</b></div>
      <div><span class="label">Déficit restante</span><b>${fmt(defDepois)}</b><span class="small muted">de ${fmt(defAntes)}</span></div>`;
    const cor = { Alta: "--critical", "Média": "--warning", Baixa: "--muted" };
    $("#prio tbody").innerHTML = cands.slice(0, 30).map((r, i) => {
      const a = add.get(r.cod_ibge) || 0;
      return `<tr class="${a ? "alloc" : ""}">
        <td class="mono">${i + 1}</td><td>${r.municipio}</td><td class="mono">${r.uf}</td>
        <td class="r">${fmt(r.populacao)}</td><td class="r">${fmt(r.pontos)}</td><td class="r">${fmt(r.pontos_necessarios)}</td>
        <td class="r">${fmt(r.deficit_pontos)}</td><td class="r">${fmt(r.hab_por_ponto)}</td><td class="r">${fmt(r.kg_hab, nf3)}</td>
        <td class="r mono">${fmt(r.indice_prioridade, nf1)}</td>
        <td><span class="pill"><i class="dot" style="background:var(${cor[r.classe_prioridade]})"></i>${r.classe_prioridade}</span></td>
        <td class="r mono">${a ? "+" + a : "–"}</td></tr>`;
    }).join("");
  }

  /* ---------------- cidadão ---------------- */
  function onBusca() {
    const v = $("#busca").value.trim();
    const m = v.match(/^(.*) – ([A-Z]{2})$/);
    let i = -1;
    if (m) i = M.nome.findIndex((n, k) => n === m[1] && M.uf[k] === m[2]);
    if (i < 0) { const t = v.toLowerCase(); i = M.nome.findIndex((n) => n.toLowerCase() === t); }
    if (i < 0) { const t = v.toLowerCase(); i = M.nome.findIndex((n) => n.toLowerCase().startsWith(t)); }
    if (i >= 0) { S.city = i; store.set("reee_city", i); renderCidade(); }
  }
  function vizinhosComPonto(i, j, k = 3) {
    const toRad = Math.PI / 180, out = [];
    for (let x = 0; x < M.n; x++) {
      if (x === i || M.pontos[x][j] === 0) continue;
      const dLat = (M.lat[x] - M.lat[i]) * toRad, dLon = (M.lon[x] - M.lon[i]) * toRad;
      const a = Math.sin(dLat / 2) ** 2 + Math.cos(M.lat[i] * toRad) * Math.cos(M.lat[x] * toRad) * Math.sin(dLon / 2) ** 2;
      out.push({ x, km: 6371 * 2 * Math.asin(Math.sqrt(a)) });
    }
    return out.sort((a, b) => a.km - b.km).slice(0, k);
  }
  function renderCidade() {
    if (!D || S.city === null) return;
    const i = S.city, j = anoIdx(), st = statusMun(i, j), pts = M.pontos[i][j];
    const ton = M.ton[i][j], kg = ton === null ? null : (ton * 1000) / M.pop[i];
    const u = ufRow(M.uf[i]), b = brRow();
    const msgs = {
      cumpre: `Cumpre a cobertura mínima do Decreto 10.240/2020: ${fmt(pts)} pontos para ${fmt(M.pop[i])} habitantes (mínimo ${st.nec}).`,
      parcial: `Tem ${fmt(pts)} pontos, mas a regra pede ${st.nec} (1 a cada 25 mil habitantes). Faltam ${st.nec - pts}.`,
      sem: `Cidade com mais de 80 mil habitantes e nenhum ponto de recebimento registrado. A regra pede ${st.nec}.`,
      livre: `Abaixo de 80 mil habitantes, a cidade não é obrigada pelo Decreto, mas já conta com ponto de recebimento.`,
      nenhum: `Abaixo de 80 mil habitantes, a cidade não é obrigada pelo Decreto e não tem ponto registrado.`,
    };
    let viz = "";
    if (pts === 0) {
      const v = vizinhosComPonto(i, j);
      viz = `<div class="small"><span class="label">Cidades mais próximas com ponto</span>
        <div class="list">${v.map((o) => `<div class="item"><b>${M.nome[o.x]} – ${M.uf[o.x]}</b><span class="muted">${fmt(o.km)} km em linha reta · ${M.pontos[o.x][j]} ponto(s)</span></div>`).join("")}</div></div>`;
    }
    const cmp = [
      { k: M.nome[i], v: kg }, { k: "UF " + M.uf[i], v: u.kg_hab }, { k: "Brasil", v: b.kg_hab },
    ];
    const max = d3.max(cmp, (c) => c.v || 0) || 1;
    $("#cidade").innerHTML = `
      <div class="city-head">
        <span class="label">${ufNome(M.uf[i])} · ${fmt(M.pop[i])} habitantes · ${S.ano}</span>
        <span class="big">${M.nome[i]}</span>
        <p>${pts > 0 ? `<b class="num">${fmt(pts)}</b> ponto${pts > 1 ? "s" : ""} de recebimento de eletroeletrônicos ativo${pts > 1 ? "s" : ""}.` : "Nenhum ponto de recebimento ativo registrado."}</p>
      </div>
      <div class="status-line"><i class="dot" style="background:var(${st.c})"></i><p><b>${st.t}.</b> ${msgs[st.k]}</p></div>
      ${viz}
      <div class="compare"><span class="label">Coleta per capita (kg/hab.)</span>
        ${cmp.map((c, n) => `<div class="bar-row"><span>${c.k}</span><span class="track"><span class="fill" style="width:${((c.v || 0) / max) * 100}%;background:var(${n === 0 ? "--series-1" : "--axis"})"></span></span><span class="v">${c.v === null ? "sem dado" : fmt(c.v, nf3)}</span></div>`).join("")}
      </div>
      <div><span class="label">Pontos ativos por ano</span><div class="chart-box" style="height:140px"><canvas id="c-cidade"></canvas></div></div>
      <div><button class="btn ghost" type="button" id="sugerir">Sugerir um ponto em ${M.nome[i]}</button></div>`;
    $("#busca").placeholder = `${M.nome[i]} – ${M.uf[i]}`;
    $("#sugerir").addEventListener("click", () => {
      $("#p-mun").value = `${M.nome[i]} – ${M.uf[i]}`; $("#p-tipo").selectedIndex = 0; $("#p-local").focus();
    });
    const s1 = css("--series-1");
    mk("c-cidade", { type: "line", data: { labels: D.meta.anos, datasets: [{ label: "Pontos", data: M.pontos[i], borderColor: s1,
      backgroundColor: s1 + "22", fill: true, borderWidth: 2, tension: 0.2, pointRadius: D.meta.anos.map((_, k) => (k === j ? 5 : 2)),
      pointBackgroundColor: s1, pointBorderColor: css("--surface"), pointBorderWidth: 2 }] },
      options: { ...baseOpts(), plugins: { legend: { display: false }, tooltip: baseOpts().plugins.tooltip },
        scales: { ...baseOpts().scales, y: { ...baseOpts().scales.y, ticks: { ...baseOpts().scales.y.ticks, precision: 0 } } } } });
    if (!$("#p-mun").value) $("#p-mun").value = `${M.nome[i]} – ${M.uf[i]}`;
  }

  /* ---------------- e-participação ---------------- */
  async function copiar(texto, toast) {
    try { await navigator.clipboard.writeText(texto); toast.textContent = "Copiado para a área de transferência."; }
    catch {
      const ta = document.createElement("textarea"); ta.value = texto; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); toast.textContent = "Copiado."; } catch { toast.textContent = "Selecione e copie manualmente."; }
      ta.remove();
    }
  }
  const csvCell = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;

  function initParticipacao() {
    const lista = () => store.get("reee_contrib", []);
    const draw = () => {
      const l = lista();
      $("#p-lista").innerHTML = l.length ? l.slice().reverse().map((c) => `<div class="item"><b>${c.tipo}</b><span>${c.municipio}${c.local ? " · " + c.local : ""}</span><span class="muted">${c.descricao}</span><span class="muted mono">${c.data.slice(0, 16).replace("T", " ")}</span></div>`).join("")
        : `<p class="small muted">Nenhuma contribuição registrada neste navegador ainda. Use o formulário acima para enviar a primeira.</p>`;
    };
    $("#form-part").addEventListener("submit", (e) => {
      e.preventDefault();
      const desc = $("#p-desc").value.trim(), mun = $("#p-mun").value.trim();
      const t = $("#p-toast");
      if (!mun || desc.length < 10) { t.textContent = "Informe o município e descreva a contribuição em pelo menos 10 caracteres."; return; }
      const l = lista();
      l.push({ tipo: $("#p-tipo").value, municipio: mun, local: $("#p-local").value.trim(), descricao: desc, data: new Date().toISOString() });
      t.textContent = store.set("reee_contrib", l) ? "Contribuição registrada." : "Este navegador bloqueou o armazenamento local; copie o texto antes de sair.";
      $("#p-desc").value = ""; $("#p-local").value = ""; draw();
    });
    $("#p-copiar").addEventListener("click", () => {
      const l = lista();
      const csv = ["tipo,municipio,local,descricao,data", ...l.map((c) => [c.tipo, c.municipio, c.local, c.descricao, c.data].map(csvCell).join(","))].join("\n");
      copiar(csv, $("#p-toast"));
    });
    draw();
  }

  const ITENS = [
    "Encontrei com facilidade a situação da minha cidade.",
    "O mapa e os gráficos são fáceis de entender.",
    "Confio na origem e no método dos dados.",
    "O painel me ajuda a cobrar o poder público.",
    "O ranking de prioridade ajudaria a planejar novos pontos.",
    "Eu voltaria a usar este painel.",
  ];
  function initAvaliacao() {
    const f = $("#form-aval");
    f.innerHTML = `<label class="field"><span>Seu perfil</span><select id="a-perfil"><option>Cidadão</option><option>Gestor público</option><option>Pesquisador</option><option>Outro</option></select></label>` +
      ITENS.map((t, k) => `<fieldset><legend>${k + 1}. ${t}</legend><div class="opts">${[1, 2, 3, 4, 5].map((v) => `<label><input type="radio" name="q${k}" id="q${k}-${v}" value="${v}"><span>${v}</span></label>`).join("")}</div></fieldset>`).join("");
    const resp = () => store.get("reee_aval", []);
    const resumo = () => {
      const r = resp();
      if (!r.length) { $("#a-resumo").innerHTML = `<p class="muted">Nenhuma avaliação registrada neste navegador.</p>`; return; }
      const med = ITENS.map((_, k) => d3.mean(r, (x) => x.notas[k]));
      $("#a-resumo").innerHTML = `<span class="label">Média de ${r.length} avaliação(ões) neste navegador</span>
        <div class="bars">${med.map((m, k) => `<div class="bar-row" style="grid-template-columns:2rem minmax(0,1fr) 3rem;cursor:default"><span class="mono">Q${k + 1}</span><span class="track"><span class="fill" style="width:${(m / 5) * 100}%"></span></span><span class="v">${m ? fmt(m, nf1) : "–"}</span></div>`).join("")}</div>`;
    };
    $("#a-salvar").addEventListener("click", () => {
      const notas = ITENS.map((_, k) => { const x = f.querySelector(`input[name="q${k}"]:checked`); return x ? +x.value : null; });
      if (notas.some((n) => n === null)) { $("#a-toast").textContent = "Responda todas as afirmações antes de enviar."; return; }
      const r = resp(); r.push({ perfil: $("#a-perfil").value, notas, data: new Date().toISOString() });
      $("#a-toast").textContent = store.set("reee_aval", r) ? "Avaliação registrada. Obrigado!" : "O navegador bloqueou o armazenamento local.";
      f.querySelectorAll("input:checked").forEach((x) => (x.checked = false)); resumo();
    });
    $("#a-copiar").addEventListener("click", () => {
      const r = resp();
      const csv = ["perfil," + ITENS.map((_, k) => "q" + (k + 1)).join(",") + ",data", ...r.map((x) => [x.perfil, ...x.notas, x.data].map(csvCell).join(","))].join("\n");
      copiar(csv, $("#a-toast"));
    });
    resumo();
  }

  /* ---------------- dados abertos ---------------- */
  function renderDados() {
    const arqs = [
      ["data/abertos/indicadores_brasil_ano.csv", "Série nacional 2019–2025 com metas do Decreto"],
      ["data/abertos/indicadores_uf_ano.csv", "Indicadores por UF e ano"],
      ["data/abertos/indicadores_municipio_ano.csv", "Indicadores por município e ano"],
      ["data/abertos/prioridade_novos_pontos.csv", "Ranking de prioridade para novos pontos"],
      ["data/abertos/municipios.csv", "Cadastro de municípios com população"],
      ["data/dashboard.json", "Pacote completo usado por este painel"],
    ];
    $("#arquivos tbody").innerHTML = arqs.map(([p, d]) => `<tr><td><a class="mono" href="${p}" target="_blank" rel="noopener">${p.split("/").pop()}</a></td><td style="white-space:normal">${d}</td></tr>`).join("");
    const rot = {
      fonte: "Fonte dos dados", pontos_linhas_lidas: "Linhas de pontos lidas", pontos_inativos_removidos: "Pontos inativos removidos",
      pontos_codigo_recuperado_por_nome: "Código IBGE recuperado pelo nome", pontos_sem_municipio_descartados: "Pontos sem município identificável",
      pontos_duplicados_removidos: "Registros duplicados removidos", pontos_registros_validos: "Registros válidos (ponto × ano)",
      pontos_fora_do_periodo: "Fora de 2019–2025", massa_linhas_lidas: "Linhas de massa lidas", massa_valores_invalidos: "Valores de massa inválidos",
      massa_outliers_sinalizados: "Valores atípicos sinalizados", massa_codigo_recuperado_por_nome: "Massa: código recuperado pelo nome",
      massa_sem_municipio_descartados: "Massa: sem município identificável",
    };
    $("#qualidade tbody").innerHTML = Object.entries(D.qualidade).filter(([, v]) => !Array.isArray(v))
      .map(([k, v]) => `<tr><td style="white-space:normal">${rot[k] || k}</td><td class="r mono">${typeof v === "number" ? fmt(v) : v}</td></tr>`).join("");
    $("#gerado").textContent = D.meta.gerado_em.replace("T", " ").replace("+00:00", " UTC");
    $("#fonte").textContent = D.meta.fonte === "demo" ? "demonstração (sintética)" : "SINIR/IBGE";
  }

  load().catch((e) => {
    $("main").insertAdjacentHTML("afterbegin", `<div class="card" style="margin-top:16px"><h2>Não foi possível carregar os dados</h2><p>Rode <span class="mono">python -m reee.pipeline --demo</span> e sirva a pasta <span class="mono">dashboard/</span> por HTTP (ex.: <span class="mono">python -m http.server</span>). Detalhe: ${e.message}</p></div>`);
  });
})();
