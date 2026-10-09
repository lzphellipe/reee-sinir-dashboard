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
  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
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
    cobertura_nominal: { label: "Pontos informados ÷ exigidos (%)", f: (v) => fmt(v, nf1) + " %" },
    deficit_nominal: { label: "Pontos que faltam (nominal)", f: (v) => fmt(v) },
    municipios_atendidos: { label: "Municípios atendidos (informado)", f: (v) => fmt(v) },
    pct_planos_reee: { label: "% dos planos municipais que citam REEE", f: (v) => fmt(v, nf1) + " %" },
  };
  const IND_MUNICIPAL = ["pontos_100k", "pct_pop_coberta", "pct_obrigados_com_ponto", "kg_hab", "deficit_pontos"];
  const IND_REL = ["cobertura_nominal", "pontos_100k", "deficit_nominal", "municipios_atendidos", "kg_hab"];
  const REL = () => D && D.meta.fonte === "relatorios_entidades";
  function montarIndicadores() {
    const temPlanos = D.uf_ano.some((r) => r.pct_planos_reee !== null && r.pct_planos_reee !== undefined);
    const lista = (REL() ? IND_REL : IND_MUNICIPAL).concat(temPlanos ? ["pct_planos_reee"] : []);
    if (!lista.includes(S.ind)) S.ind = lista[0];
    $("#f-ind").innerHTML = lista.map((k) => `<option value="${k}"${k === S.ind ? " selected" : ""}>${IND[k].label}</option>`).join("");
  }

  let D, GEO, M; // pacote, geojson, municípios
  const S = { ano: null, uf: "", ind: "pontos_100k", city: null };
  const charts = {};

  /* ---------------- carga ---------------- */
  let iniciado = false;
  async function load() {
    const pegar = (u) => fetch(u, { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error(`${u}: HTTP ${r.status}`); return r.json(); });
    const [d, g] = await Promise.all([pegar("data/dashboard.json"), GEO ? GEO : pegar("data/uf.geojson")]);
    D = d; GEO = g; M = d.municipios;
    M.n = M.cod.length;
    M.idx = new Map(M.cod.map((c, i) => [c, i]));
    M.planos = new Map();  // cod_ibge -> [{ano, reee, lr, trecho}]
    for (const [cod, ano, reee, lr, trecho] of d.planos_mun || []) {
      if (!M.planos.has(cod)) M.planos.set(cod, []);
      M.planos.get(cod).push({ ano, reee, lr, trecho });
    }
    if (S.city !== null && S.city >= M.n) S.city = null;
    const comDados = d.meta.anos_com_dados && d.meta.anos_com_dados.length ? d.meta.anos_com_dados : d.meta.anos;
    if (!iniciado || !comDados.includes(S.ano)) {
      S.ano = comDados[comDados.length - 1];
      if (d.meta.fonte === "relatorios_entidades") {  // ano em que mais entidades publicaram relatório
        const n = (r) => (r.entidades ? r.entidades.split(",").length : 0) * 10 + (r.pontos ? 1 : 0);
        S.ano = d.brasil_ano.filter((r) => comDados.includes(r.ano)).reduce((a, b) => (n(b) >= n(a) ? b : a)).ano;
      }
    }
    montarIndicadores();
    if (!iniciado) { init(); iniciado = true; } else { renderDados(); render(); }
    $$("#years button").forEach((b) => {
      const tem = comDados.includes(+b.dataset.ano);
      b.classList.toggle("sem-dados", !tem);
      b.title = tem ? "" : "Sem dados de eletroeletrônicos neste ano";
      b.setAttribute("aria-pressed", +b.dataset.ano === S.ano);
    });
    atualizarBanner();
    if (!apiOk) mostrarStatusEstatico();
  }

  const ROTULO_FONTE = { demo: "sintéticos de demonstração", sinir_estados_municipios: "do SINIR (módulo Estados e Municípios)", sinir_arquivos: "do SINIR", relatorios_entidades: "dos relatórios das entidades gestoras (SINIR)" };
  const quando = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "–");

  function atualizarBanner() {
    const demo = D.meta.fonte === "demo";
    $("#banner").hidden = false;
    if (REL()) {
      $("#banner-chip").textContent = "Relatórios das entidades";
      const anos = D.brasil_ano.filter((r) => r.entidades).map((r) => `${r.ano}: ${r.entidades}`);
      $("#banner-txt").textContent = `Dados reais dos relatórios anuais das entidades gestoras publicados no SINIR (${anos.join(" · ")}). ` +
        "Os números são por estado: o SINIR não publica a lista de pontos por município. Anos sem relatório de uma entidade não são comparáveis aos demais.";
      return;
    }
    $("#banner-chip").textContent = demo ? "Dados sintéticos" : "Dados declarados";
    if (demo) {
      $("#banner-txt").textContent = "Esta versão usa dados de demonstração gerados no formato do SINIR. Os números não descrevem a situação real" +
        (apiOk ? "; clique em Atualizar dados para buscar os dados oficiais." : ".");
      return;
    }
    const comInfo = D.brasil_ano.filter((r) => r.municipios_com_info > 0).map((r) => r.ano);
    const b = brRow(comInfo[comInfo.length - 1] ?? D.meta.anos[D.meta.anos.length - 1]);
    const aviso = D.qualidade.aviso ? ` Atenção: ${D.qualidade.aviso}` : "";
    $("#banner-txt").textContent = `Informações autodeclaradas pelos municípios ao SINIR. ` +
      (comInfo.length ? `Há dados de eletroeletrônicos para ${comInfo.join(", ")}; em ${b.ano}, ${fmt(b.pct_municipios_com_info, nf1)} % dos municípios informaram. ` : "") +
      `Municípios que não informaram aparecem como "sem informação".${aviso}`;
  }

  /* ---------------- status / atualização em tempo de execução ---------------- */
  let apiOk = false, ultimoEstado = null, aguardandoDados = false, timerStatus = null;
  function pintarStatus(cor, texto, pulsar = false) {
    $("#statusbar").hidden = false;
    $("#st-dot").style.background = `var(${cor})`;
    $("#st-dot").classList.toggle("pulse", pulsar);
    $("#st-texto").textContent = texto;
  }
  function mostrarStatusEstatico() {
    if (!D) return;
    pintarStatus("--good", `Dados ${ROTULO_FONTE[D.meta.fonte] || D.meta.fonte} · gerados em ${quando(D.meta.gerado_em)}`);
    $("#st-btn").hidden = true; $("#st-log").hidden = true;
  }
  async function checarStatus() {
    clearTimeout(timerStatus);
    let st;
    try {
      const r = await fetch("api/status", { cache: "no-store" });
      if (!r.ok) throw new Error();
      st = await r.json();
      apiOk = true;
    } catch { apiOk = false; mostrarStatusEstatico(); return null; }
    $("#st-btn").hidden = false; $("#st-log").hidden = false;
    $("#st-btn").disabled = st.estado === "executando";
    $("#st-log-txt").textContent = st.log.join("\n") || "Nenhuma atualização nesta sessão.";
    const dados = st.dados ? `Dados ${ROTULO_FONTE[st.dados.fonte] || st.dados.fonte} · gerados em ${quando(st.dados.gerado_em)}` : "Ainda não há dados";
    if (st.estado === "executando") pintarStatus("--warning", `Atualizando · ${st.etapa || "iniciando"}`, true);
    else if (st.estado === "erro") pintarStatus("--critical", `A última atualização falhou: ${st.erro}. ${st.dados ? "Mostrando os dados anteriores." : ""}`);
    else pintarStatus("--good", dados);
    if (st.estado === "executando") timerStatus = setTimeout(checarStatus, 1500);
    else if (ultimoEstado === "executando" || (aguardandoDados && st.dados)) {
      try { await load(); aguardandoDados = false; $("#espera")?.remove(); } catch (e) { /* segue aguardando */ }
    }
    ultimoEstado = st.estado;
    return st;
  }
  async function pedirAtualizacao(forcar = false) {
    $("#st-btn").disabled = true;
    try { await fetch(`api/atualizar${forcar ? "?forcar=1" : ""}`, { method: "POST" }); } catch { /* status mostra */ }
    ultimoEstado = "executando";
    checarStatus();
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
    renderKPIs(); renderMap(); renderRank(); renderCharts(); renderEntidades(); renderPlanos(); renderPrio(); renderCidade();
  }

  /* ---------------- planos municipais (texto livre declarado ao SINIR) ---------------- */
  function renderPlanos() {
    const card = $("#card-planos");
    const fonte = S.uf ? D.uf_ano.filter((r) => r.uf === S.uf) : D.brasil_ano;
    const temDado = (D.planos_uf || []).length > 0;
    card.hidden = !temDado;
    if (!temDado) return;
    const anos = D.meta.anos, rows = anos.map((a) => fonte.find((r) => r.ano === a) || {});
    const o = baseOpts("municípios");
    mk("c-planos", { type: "bar", data: { labels: anos, datasets: [
      { label: "Declararam o plano", data: rows.map((r) => r.planos_declarados ?? null), backgroundColor: css("--axis"), borderRadius: 3, maxBarThickness: 30 },
      { label: "Citam eletroeletrônicos", data: rows.map((r) => r.planos_citam_reee ?? null), backgroundColor: css("--series-1"), borderRadius: 3, maxBarThickness: 30 },
    ] }, options: o });
    const r = fonte.find((x) => x.ano === S.ano) || {};
    const lugar = S.uf ? ufNome(S.uf) : "no Brasil";
    $("#planos-resumo").innerHTML = r.planos_declarados
      ? `<p><b class="num">${fmt(r.planos_citam_reee)}</b> de ${fmt(r.planos_declarados)} municípios que declararam o plano ${S.uf ? "em " + lugar : lugar} em ${S.ano} citam ações para eletroeletrônicos (<b>${fmt(r.pct_planos_reee, nf1)} %</b>).</p>
         <p class="muted">Classificação por palavras-chave nas metas, programas e soluções compartilhadas. Citar não prova que a ação foi executada; não citar não prova que ela não exista. Os trechos aparecem na ficha de cada cidade, na aba Cidadão.</p>`
      : `<p class="muted">Nenhum município ${S.uf ? "de " + lugar + " " : ""}declarou o plano ao SINIR em ${S.ano}.</p>`;
  }
  function planoHtml(i) {
    if (!(D.planos_mun || []).length) return "";
    const lista = (M.planos.get(M.cod[i]) || []).slice().sort((a, b) => b.ano - a.ano);
    const anosArq = [...new Set(D.planos_mun.map((p) => p[1]))].sort();
    const sem = anosArq.filter((a) => !lista.some((p) => p.ano === a));
    const itens = lista.map((p) => p.reee
      ? `<div class="item"><b>${p.ano} · cita eletroeletrônicos</b><span>“${esc(p.trecho)}”</span></div>`
      : `<div class="item"><b>${p.ano} · sem menção a eletroeletrônicos</b><span class="muted">O plano foi declarado${p.lr ? " e cita logística reversa de outros resíduos" : ""}, mas não fala de REEE.</span></div>`).join("");
    return `<div><span class="label">Plano municipal de resíduos declarado ao SINIR</span>
      ${lista.length ? `<div class="list">${itens}</div>` : `<p class="small">A prefeitura não declarou o plano ao SINIR entre ${anosArq[0]} e ${anosArq[anosArq.length - 1]}. Você pode pedir o plano municipal de gestão de resíduos pela Lei de Acesso à Informação.</p>`}
      ${lista.length && sem.length ? `<p class="small muted">Sem declaração em ${sem.join(", ")}.</p>` : ""}
      <p class="small muted">Leitura automática do texto declarado pela prefeitura: citar não prova execução.</p></div>`;
  }

  /* ---------------- KPIs ---------------- */
  function delta(cur, prev) {
    if (!prev || cur === null || cur === undefined) return "";
    const d = ((cur - prev) / prev) * 100;
    const cls = d >= 0 ? "up" : "down";
    return `<span class="delta ${cls} mono">${d >= 0 ? "▲" : "▼"} ${fmt(Math.abs(d), nf1)} %</span> vs ${S.ano - 1}`;
  }
  function renderKPIsRel() {
    const r = scopeRow(), p = scopeRow(S.ano - 1), lugar = S.uf ? ufNome(S.uf) : "Brasil";
    const quem = r.entidades ? `Informado por ${r.entidades}` : "Nenhuma entidade publicou dados deste recorte";
    const mesmo = p && p.entidades === r.entidades;  // variação só entre anos com as mesmas entidades
    $("#k-pontos").innerHTML = `<span class="label">Pontos de recebimento · ${lugar}</span>
      <div><span class="value">${fmt(r.pontos)}</span></div>
      <div class="sub">${mesmo ? delta(r.pontos, p.pontos) : ""}</div>
      <div class="sub">${fmt(r.pontos_100k, nf2)} por 100 mil habitantes</div><div class="sub">${quem}</div>`;
    $("#k-massa").innerHTML = `<span class="label">REEE coletado · ${S.ano}</span>
      <div><span class="value">${fmt(r.toneladas)}</span><span class="unit">t</span></div>
      <div class="sub">${fmt(r.kg_hab, nf3)} kg/hab.</div>
      <div class="sub">${S.uf && r.toneladas === null && r.pontos !== null ? "Esta entidade não informa massa por estado" : ""}</div>`;
    const meta = D.meta.metas_decreto[S.ano];
    $("#k-meta").innerHTML = `<span class="label">Municípios atendidos (informado)</span>
      <div><span class="value">${fmt(r.municipios_atendidos)}</span></div>
      ${!S.uf && meta ? `<span class="pill"><i class="dot" style="background:var(--muted)"></i>Meta do Decreto: ${fmt(meta.municipios)} municípios acima de 80 mil</span>` : ""}
      <div class="sub">Soma das entidades; um município atendido pelas duas conta duas vezes.</div>`;
    const cob = r.cobertura_nominal;
    const cor = cob === null || cob === undefined ? "--muted" : cob >= 100 ? "--good" : cob >= 50 ? "--warning" : "--critical";
    $("#k-deficit").innerHTML = `<span class="label">Pontos informados ÷ exigidos</span>
      <div><span class="value">${cob === null || cob === undefined ? "–" : fmt(cob, nf1)}</span><span class="unit">%</span></div>
      <span class="pill"><i class="dot" style="background:var(${cor})"></i>${fmt(r.pontos)} de ${fmt(r.pontos_exigidos)} exigidos</span>
      <div class="sub">Exigidos: 1 ponto a cada 25 mil hab. nos municípios acima de 80 mil (Censo 2022).</div>`;
  }
  function renderKPIs() {
    if (REL()) return renderKPIsRel();
    const r = scopeRow(), p = scopeRow(S.ano - 1);
    if (r.municipios_com_info === 0) {
      const sem = (rot) => `<span class="label">${rot}</span><div><span class="value">–</span></div><div class="sub">Nenhum município informou dados de eletroeletrônicos em ${S.ano}.</div>`;
      $("#k-pontos").innerHTML = sem(`Pontos ativos · ${S.uf ? ufNome(S.uf) : "Brasil"}`);
      $("#k-massa").innerHTML = sem(`REEE recebido · ${S.ano}`);
      $("#k-meta").innerHTML = sem("Municípios &gt; 80 mil hab. com ponto");
      $("#k-deficit").innerHTML = sem("Pontos faltantes (1 a cada 25 mil hab.)");
      return;
    }
    const lugar = S.uf ? ufNome(S.uf) : "Brasil";
    $("#k-pontos").innerHTML = `<span class="label">Pontos ativos · ${lugar}</span>
      <div><span class="value">${fmt(r.pontos)}</span></div>
      <div class="sub">${delta(r.pontos, p && p.pontos)}</div>
      <div class="sub">${fmt(r.pontos_100k, nf2)} por 100 mil habitantes</div>
      ${D.meta.fonte !== "demo" ? `<div class="sub">Informação de ${fmt(r.municipios_com_info)} de ${fmt(r.municipios)} municípios</div>` : ""}`;
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
      <div class="sub">${fmt(r.obrigados_cumprem)} de ${fmt(r.obrigados)} municípios obrigados cumprem a densidade mínima</div>
      ${r.obrigados_sem_info ? `<div class="sub">${fmt(r.obrigados_sem_info)} obrigados sem informação ficam fora da conta</div>` : ""}`;
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
    if (pts === null) return { k: "semdado", c: "--muted", t: "Sem informação no SINIR", nec: nec || undefined };
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

    // municípios (não há dado municipal no modo de relatórios)
    const j = anoIdx(), pts = [];
    for (let i = 0; i < (REL() ? 0 : M.n); i++) {
      if (S.uf && M.uf[i] !== S.uf) continue;
      const st = statusMun(i, j);
      if (!S.uf && st.nec === undefined) continue;
      if (S.uf && (st.k === "nenhum" || (st.k === "semdado" && st.nec === undefined))) continue;
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
      ${REL() ? `<span class="muted">Dados por estado. Clique em um estado para filtrar.</span>` : `<span><i class="dot" style="background:var(--good)"></i> Cumpre 1 ponto/25 mil hab.</span>`}
      ${REL() ? "" : `<span><i class="dot" style="background:var(--warning)"></i> Tem ponto, com déficit</span>
      <span><i class="dot" style="background:var(--critical)"></i> Obrigado e sem ponto</span>`}
      ${D.meta.fonte !== "demo" && !REL() ? `<span><i class="dot" style="background:var(--muted)"></i> Sem informação</span>` : ""}
      ${S.uf ? `<span><i class="dot" style="background:var(--accent)"></i> Abaixo de 80 mil hab. com ponto</span>` : ""}`;
  }

  /* ---------------- ranking UF ---------------- */
  function renderRank() {
    const rows = D.uf_ano.filter((r) => r.ano === S.ano && r[S.ind] !== null).sort((a, b) => b[S.ind] - a[S.ind]);
    const max = d3.max(rows, (r) => r[S.ind]) || 1;
    $("#rank-sub").textContent = `${IND[S.ind].label}, ${S.ano}. Clique para filtrar.`;
    if (!rows.length) { $("#rank").innerHTML = `<p class="empty-state">Sem dados deste indicador em ${S.ano}.</p>`; return; }
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

  function serieEntidade(campo) {
    // valores por entidade e ano no recorte atual (Brasil: totais nacionais; UF: tabela por UF)
    const fonte = S.uf ? D.uf_entidade.filter((r) => r.uf === S.uf) : D.entidade_ano;
    const ents = [...new Set(fonte.map((r) => r.entidade))].sort();
    return ents.map((e) => ({ e, v: D.meta.anos.map((a) => { const r = fonte.find((x) => x.entidade === e && x.ano === a); return r && r[campo] !== null ? r[campo] : null; }) }));
  }
  const tituloCard = (id, t, sub) => { const c = $("#" + id).closest(".card"); c.querySelector("h2").textContent = t; if (sub !== undefined) c.querySelector("header p").textContent = sub; };
  function renderChartsRel() {
    const anos = D.meta.anos, cores = [css("--series-1"), css("--series-2"), css("--series-3")];
    tituloCard("c-pontos", "Pontos de recebimento informados", "Por ano e entidade gestora; ano sem barra = sem relatório publicado");
    tituloCard("c-meta", "Municípios atendidos x meta", "Informado pelas entidades; meta acumulada do Decreto 10.240/2020");
    const empilhado = (id, campo, titulo, extra = []) => {
      const ds = serieEntidade(campo).map((s, k) => ({ type: "bar", label: s.e, data: s.v, backgroundColor: cores[k % 3], borderRadius: 3, maxBarThickness: 36, stack: "e" }));
      const o = baseOpts(titulo);
      o.scales.x.stacked = true; o.scales.y.stacked = true;
      mk(id, { data: { labels: anos, datasets: [...ds, ...extra] }, options: o });
    };
    empilhado("c-pontos", "pontos", "pontos");
    const meta = anos.map((a) => (S.uf ? null : D.meta.metas_decreto[a]?.municipios ?? null));
    empilhado("c-meta", "municipios_atendidos", "municípios", S.uf ? [] : [{ type: "line", label: "Meta do Decreto", data: meta,
      borderColor: css("--ink-2"), borderDash: [5, 4], pointRadius: 4, pointBackgroundColor: css("--ink-2"), borderWidth: 2, stack: "meta" }]);
    empilhado("c-massa", "toneladas", "t");
    $("#massa-sub").textContent = S.uf ? "Toneladas por ano · só a ABREE informa massa por estado (2022)" : "Toneladas por ano e entidade · 2019–2021 só ABREE; 2023 só Green Eletron";
  }
  function renderCharts() {
    if (REL()) return renderChartsRel();
    tituloCard("c-pontos", "Pontos de recebimento ativos", "Por ano, recorte selecionado");
    tituloCard("c-meta", "Municípios obrigados com ponto x meta", "Meta acumulada do Decreto 10.240/2020 (fase 2)");
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
    const base = REL() && S.uf ? D.uf_entidade.filter((r) => r.uf === S.uf) : D.entidade_ano;
    $("#ent-sub").textContent = `${REL() && S.uf ? ufNome(S.uf) : "Brasil"}, ${S.ano}`;
    const e = base.filter((r) => r.ano === S.ano && r.pontos !== null).map((r) => ({ k: r.entidade, v: r.pontos })).sort((a, b) => b.v - a.v);
    const t = D.tipo_ano.filter((r) => r.ano === S.ano).map((r) => ({ k: r.tipo, v: r.pontos })).sort((a, b) => b.v - a.v);
    const vazio = `<p class="empty-state">Esta fonte não detalha entidade gestora nem tipo de ponto.</p>`;
    if (e.length) hbars($("#entidades"), e, css("--series-1")); else $("#entidades").innerHTML = vazio;
    if (t.length) hbars($("#tipos"), t, css("--series-3")); else $("#tipos").innerHTML = "";
    $("#tipos-titulo").hidden = !t.length;
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
  const PRIO_HEAD = $("#prio thead").innerHTML;
  function renderPrioRel() {
    $(".sim").hidden = true; $("#prio-nota").hidden = true;
    const rows = D.uf_ano.filter((r) => r.ano === S.ano && r.pontos !== null && (!S.uf || r.uf === S.uf))
      .sort((a, b) => (b.deficit_nominal ?? -1) - (a.deficit_nominal ?? -1));
    $("#prio-sub").textContent = `Estados ordenados pelos pontos que faltam para a regra do Decreto (${S.ano}, ${D.brasil_ano.find((r) => r.ano === S.ano)?.entidades || "sem relatório"}). A priorização por município exige o dado municipal do SINIR.`;
    $("#prio thead").innerHTML = `<tr><th>#</th><th>UF</th><th class="r">População</th><th class="r">Municípios &gt; 80 mil</th><th class="r">Pontos exigidos</th><th class="r">Pontos informados</th><th class="r">Faltam</th><th class="r">Informados ÷ exigidos</th><th>Situação</th></tr>`;
    $("#prio tbody").innerHTML = rows.length ? rows.map((r, i) => {
      const c = r.cobertura_nominal, cor = c >= 100 ? "--good" : c >= 50 ? "--warning" : "--critical";
      const txt = c >= 100 ? "Atende em número" : c >= 50 ? "Abaixo do exigido" : "Muito abaixo";
      return `<tr><td class="mono">${i + 1}</td><td>${ufNome(r.uf)}</td><td class="r">${fmt(r.populacao)}</td><td class="r">${fmt(r.obrigados)}</td>
        <td class="r">${fmt(r.pontos_exigidos)}</td><td class="r">${fmt(r.pontos)}</td><td class="r">${fmt(r.deficit_nominal)}</td>
        <td class="r mono">${fmt(c, nf1)} %</td><td><span class="pill"><i class="dot" style="background:var(${cor})"></i>${txt}</span></td></tr>`;
    }).join("") : `<tr><td colspan="9" class="empty-state">Nenhuma entidade publicou pontos por estado em ${S.ano}.</td></tr>`;
  }
  function renderPrio() {
    if (REL()) return renderPrioRel();
    $(".sim").hidden = false; $("#prio-nota").hidden = false;
    if ($("#prio thead").innerHTML !== PRIO_HEAD) $("#prio thead").innerHTML = PRIO_HEAD;
    const anoP = D.meta.ano_prioridade ?? D.meta.anos[D.meta.anos.length - 1];
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
      if (x === i || !(M.pontos[x][j] > 0)) continue;
      const dLat = (M.lat[x] - M.lat[i]) * toRad, dLon = (M.lon[x] - M.lon[i]) * toRad;
      const a = Math.sin(dLat / 2) ** 2 + Math.cos(M.lat[i] * toRad) * Math.cos(M.lat[x] * toRad) * Math.sin(dLon / 2) ** 2;
      out.push({ x, km: 6371 * 2 * Math.asin(Math.sqrt(a)) });
    }
    return out.sort((a, b) => a.km - b.km).slice(0, k);
  }
  function renderCidadeRel() {
    const i = S.city, pop = M.pop[i], uf = M.uf[i], u = ufRow(uf), b = brRow();
    const nec = pop > D.meta.limiar_populacional ? Math.ceil(pop / D.meta.hab_por_ponto_decreto) : 0;
    const lista = D.mun_entidade.filter((r) => r.cod_ibge === M.cod[i]);
    const comPonto = new Map(D.mun_entidade.map((r) => [r.cod_ibge, r.pontos]));
    const regra = nec ? `Com ${fmt(pop)} habitantes, a regra do Decreto 10.240/2020 pede pelo menos <b>${nec}</b> ponto${nec > 1 ? "s" : ""} de recebimento na cidade (1 a cada 25 mil hab.).`
      : `Com ${fmt(pop)} habitantes (abaixo de 80 mil), a cidade não tem meta própria no Decreto 10.240/2020.`;
    let lst = lista.length ? lista.map((r) => `<div class="item"><b>${fmt(r.pontos)} PEV${r.pontos > 1 ? "s" : ""} da ${r.entidade}</b><span class="muted">Relatório anual de ${r.ano}</span></div>`).join("")
      : `<p class="small muted">A Green Eletron não listou pontos nesta cidade no relatório de 2022. A ABREE publica só a contagem por estado.</p>`;
    let viz = "";
    if (!lista.length) {
      const toRad = Math.PI / 180, out = [];
      for (let x = 0; x < M.n; x++) {
        if (!comPonto.has(M.cod[x])) continue;
        const dLat = (M.lat[x] - M.lat[i]) * toRad, dLon = (M.lon[x] - M.lon[i]) * toRad;
        const a = Math.sin(dLat / 2) ** 2 + Math.cos(M.lat[i] * toRad) * Math.cos(M.lat[x] * toRad) * Math.sin(dLon / 2) ** 2;
        out.push({ x, km: 6371 * 2 * Math.asin(Math.sqrt(a)) });
      }
      viz = `<div class="small"><span class="label">Cidades mais próximas com PEV da Green Eletron (2022)</span><div class="list">${out.sort((a, b) => a.km - b.km).slice(0, 3)
        .map((o) => `<div class="item"><b>${M.nome[o.x]} – ${M.uf[o.x]}</b><span class="muted">${fmt(o.km)} km em linha reta · ${comPonto.get(M.cod[o.x])} PEV(s)</span></div>`).join("")}</div></div>`;
    }
    const cmp = [{ k: ufNome(uf), v: u.pontos_100k }, { k: "Brasil", v: b.pontos_100k }];
    const max = d3.max(cmp, (c) => c.v || 0) || 1;
    $("#cidade").innerHTML = `
      <div class="city-head"><span class="label">${ufNome(uf)} · Censo 2022</span><span class="big">${M.nome[i]}</span><p>${regra}</p></div>
      <div><span class="label">Pontos listados nos relatórios</span><div class="list">${lst}</div></div>
      ${viz}
      ${planoHtml(i)}
      <div class="status-line"><i class="dot" style="background:var(--muted)"></i><p>Em ${S.ano}, ${u.entidades ? `as entidades (${u.entidades}) informaram <b>${fmt(u.pontos)}</b> pontos em ${ufNome(uf)}, ${fmt(u.cobertura_nominal, nf1)} % do que a regra exige no estado.` : `nenhuma entidade publicou dados de ${ufNome(uf)}.`} Para saber o endereço dos pontos, consulte os sites da ABREE e da Green Eletron ou peça à prefeitura pela Lei de Acesso à Informação.</p></div>
      <div class="compare"><span class="label">Pontos por 100 mil habitantes · ${S.ano}</span>
        ${cmp.map((c, n) => `<div class="bar-row"><span>${c.k}</span><span class="track"><span class="fill" style="width:${((c.v || 0) / max) * 100}%;background:var(${n === 0 ? "--series-1" : "--axis"})"></span></span><span class="v">${c.v === null ? "sem dado" : fmt(c.v, nf2)}</span></div>`).join("")}
      </div>
      <div><button class="btn ghost" type="button" id="sugerir">Sugerir um ponto em ${M.nome[i]}</button></div>`;
    $("#busca").placeholder = `${M.nome[i]} – ${uf}`;
    $("#sugerir").addEventListener("click", () => { $("#p-mun").value = `${M.nome[i]} – ${uf}`; $("#p-tipo").selectedIndex = 0; $("#p-local").focus(); });
    if (!$("#p-mun").value) $("#p-mun").value = `${M.nome[i]} – ${uf}`;
  }
  function renderCidade() {
    if (!D || S.city === null) return;
    if (REL()) return renderCidadeRel();
    const i = S.city, j = anoIdx(), st = statusMun(i, j), pts = M.pontos[i][j];
    const ton = M.ton[i][j], kg = ton === null ? null : (ton * 1000) / M.pop[i];
    const u = ufRow(M.uf[i]), b = brRow();
    const msgs = {
      cumpre: `Cumpre a cobertura mínima do Decreto 10.240/2020: ${fmt(pts)} pontos para ${fmt(M.pop[i])} habitantes (mínimo ${st.nec}).`,
      parcial: `Tem ${fmt(pts)} pontos, mas a regra pede ${st.nec} (1 a cada 25 mil habitantes). Faltam ${st.nec - pts}.`,
      sem: `Cidade com mais de 80 mil habitantes e nenhum ponto de recebimento registrado. A regra pede ${st.nec}.`,
      livre: `Abaixo de 80 mil habitantes, a cidade não é obrigada pelo Decreto, mas já conta com ponto de recebimento.`,
      nenhum: `Abaixo de 80 mil habitantes, a cidade não é obrigada pelo Decreto e não tem ponto registrado.`,
      semdado: `O município não informou dados de eletroeletrônicos ao SINIR em ${S.ano}. Você pode solicitar a informação à prefeitura pela Lei de Acesso à Informação.`,
    };
    let viz = "";
    if (!(pts > 0)) {
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
        <p>${pts === null ? "Sem informação sobre pontos de recebimento neste ano." : pts > 0 ? `<b class="num">${fmt(pts)}</b> ponto${pts > 1 ? "s" : ""} de recebimento de eletroeletrônicos ativo${pts > 1 ? "s" : ""}.` : "Nenhum ponto de recebimento ativo registrado."}</p>
      </div>
      <div class="status-line"><i class="dot" style="background:var(${st.c})"></i><p><b>${st.t}.</b> ${msgs[st.k]}</p></div>
      ${viz}
      ${planoHtml(i)}
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
      abas_lidas: "Abas de planilha lidas", abas_com_codigo_ibge: "Abas com código IBGE (municipais)",
      anos_com_campo_pontos: "Anos com nº de pontos de REEE", anos_com_campo_toneladas: "Anos com massa de REEE",
      anos_com_campo_possui: "Anos com 'possui ponto de REEE'", declaracoes_municipio_ano: "Declarações município × ano",
      aviso: "Aviso", coleta_falhas: "Falhas na coleta", relatorios_validados: "Relatórios",
    };
    const corr = D.qualidade.relatorio_municipios_nome_corrigido || [];
    $("#qualidade tbody").innerHTML = (corr.length ? `<tr><td style="white-space:normal">Nomes corrigidos no casamento com o IBGE</td><td class="r mono">${corr.length}</td></tr><tr><td colspan="2" class="small muted" style="white-space:normal">${corr.join("; ")}</td></tr>` : "") + Object.entries(D.qualidade).filter(([, v]) => !Array.isArray(v))
      .map(([k, v]) => `<tr><td style="white-space:normal">${rot[k] || k}</td><td class="r mono" style="white-space:normal">${typeof v === "number" ? fmt(v) : v}</td></tr>`).join("");
    $("#gerado").textContent = D.meta.gerado_em.replace("T", " ").replace("+00:00", " UTC");
    $("#fonte").textContent = ROTULO_FONTE[D.meta.fonte] || D.meta.fonte;
    const fr = D.meta.fontes_relatorios || {};
    const linhasRel = Object.entries(fr.arquivos || {}).filter(([, a]) => a.url)
      .map(([, a]) => `<tr><td style="white-space:normal"><a href="${a.url}" target="_blank" rel="noopener">${a.documento}</a></td><td style="white-space:normal">${a.conferencia || ""}</td></tr>`);
    const falta = Object.entries(fr.nao_obtidos || {}).map(([k, v]) => `<li><b>${k}:</b> ${v}</li>`).join("");
    const relHtml = linhasRel.length ? `<h3>Relatórios usados</h3><table><thead><tr><th>Documento</th><th>Conferência dos totais</th></tr></thead><tbody>${linhasRel.join("")}</tbody></table>${falta ? `<h3>Não obtidos</h3><ul class="small">${falta}</ul>` : ""}` : "";
    const prov = Object.entries(D.meta.proveniencia || {});
    $("#proveniencia").innerHTML = prov.length ? `<table><thead><tr><th>Ano</th><th>Arquivo original</th><th>Coletado em</th></tr></thead><tbody>${
      prov.map(([a, p]) => `<tr><td class="mono">${a}</td><td style="white-space:normal"><a href="${p.url}" target="_blank" rel="noopener">${p.nome}</a></td><td class="mono">${quando(p.coletado_em)}</td></tr>`).join("")}</tbody></table>` : relHtml;
  }

  $("#st-btn").addEventListener("click", () => pedirAtualizacao(false));
  (async () => {
    const st = await checarStatus();
    try { await load(); }
    catch (e) {
      if (st) {
        aguardandoDados = true;
        $("main").insertAdjacentHTML("afterbegin", `<div class="card" id="espera" style="margin-top:16px"><h2>Buscando os dados oficiais</h2><p>O servidor está baixando e tratando os arquivos do SINIR e do IBGE. O painel abre sozinho quando terminar; acompanhe pela barra acima.</p></div>`);
        if (st.estado !== "executando") pedirAtualizacao(false);
      } else {
        $("main").insertAdjacentHTML("afterbegin", `<div class="card" style="margin-top:16px"><h2>Não foi possível carregar os dados</h2><p>Inicie o painel com <span class="mono">python -m reee.servidor</span>, que busca e trata os dados automaticamente. Detalhe: ${e.message}</p></div>`);
      }
    }
  })();
})();
