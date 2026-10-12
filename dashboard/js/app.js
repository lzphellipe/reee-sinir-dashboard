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
    pct_planos_pev: { label: "% dos planos que preveem ecoponto/PEV", f: (v) => fmt(v, nf1) + " %" },
    pct_planos_lr: { label: "% dos planos que citam logística reversa", f: (v) => fmt(v, nf1) + " %" },
    custo_conv_hab: { label: "Custo da coleta convencional (R$/hab./ano, mediana)", f: (v) => "R$ " + fmt(v, nf1) },
    custo_sel_hab: { label: "Custo da coleta seletiva (R$/hab./ano, mediana)", f: (v) => "R$ " + fmt(v, nf1) },
    pct_taxa: { label: "% dos municípios com taxa de resíduos", f: (v) => fmt(v, nf1) + " %" },
    pct_passivo: { label: "% dos municípios com passivo ambiental declarado", f: (v) => fmt(v, nf1) + " %" },
    pct_coleta_seletiva: { label: "% dos municípios com coleta seletiva (SINIR)", f: (v) => fmt(v, nf1) + " %" },
    pct_plano_gestao: { label: "% dos municípios com plano de gestão (SINIR)", f: (v) => fmt(v, nf1) + " %" },
  };
  const ANOS_V = () => D.meta.anos_painel || D.meta.anos;  // anos exibidos (delimitação do trabalho)
  const IND_MUNICIPAL = ["pontos_100k", "pct_pop_coberta", "pct_obrigados_com_ponto", "kg_hab", "deficit_pontos"];
  const IND_REL = ["cobertura_nominal", "pontos_100k", "deficit_nominal", "municipios_atendidos", "kg_hab"];
  const REL = () => D && D.meta.fonte === "relatorios_entidades";
  function montarIndicadores() {
    const nUF = (k, ano) => D.uf_ano.filter((r) => (ano === undefined || r.ano === ano) && r[k] !== null && r[k] !== undefined && r[k] !== 0).length;
    const tem = (k, ano) => nUF(k, ano) > 0;
    const extras = ["pct_coleta_seletiva", "pct_planos_pev", "custo_conv_hab", "custo_sel_hab", "pct_taxa", "pct_passivo",
      "pct_planos_reee", "pct_planos_lr", "pct_plano_gestao"].filter((k) => tem(k));
    const lista = (REL() ? IND_REL : IND_MUNICIPAL).concat(extras);
    // o mapa abre no primeiro indicador com valor em pelo menos 10 UFs no ano (contraste); senão, no primeiro com algum valor
    if (!lista.includes(S.ind) || !tem(S.ind, S.ano) || !S.indEscolhido)
      S.ind = lista.find((k) => nUF(k, S.ano) >= 10) || lista.find((k) => tem(k, S.ano)) || lista[0];
    $("#f-ind").innerHTML = lista.map((k) => `<option value="${k}"${k === S.ind ? " selected" : ""}>${IND[k].label}</option>`).join("");
  }

  let D, GEO, M; // pacote, geojson, municípios
  const S = { ano: null, uf: "", reg: null, ind: "pontos_100k", city: null };
  const charts = {};

  /* ---------------- carga ---------------- */
  let iniciado = false;
  async function load() {
    const pegar = (u) => fetch(u, { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error(`${u}: HTTP ${r.status}`); return r.json(); });
    const [d, g] = await Promise.all([pegar("data/dashboard.json"), GEO ? GEO : pegar("data/uf.geojson")]);
    D = d; GEO = g; M = d.municipios;
    // massa "0" num ano em que a entidade informou pontos é massa não publicada, não coleta zero
    // (somas de células vazias viram 0 em versões antigas do pipeline ou em CSVs salvos pelo Excel)
    for (const k of ["brasil_ano", "uf_ano", "entidade_ano", "uf_entidade"]) for (const r of D[k] || []) {
      if (r.toneladas === 0 && r.pontos > 0) { r.toneladas = null; if ("kg_hab" in r) r.kg_hab = null; }
    }
    M.n = M.cod.length;
    M.idx = new Map(M.cod.map((c, i) => [c, i]));
    M.planos = new Map();  // cod_ibge -> [{ano, reee, lr, trecho}]
    for (const [cod, ano, reee, lr, trecho, coleta, plano, pev, trechoPev] of d.planos_mun || []) {
      if (!M.planos.has(cod)) M.planos.set(cod, []);
      M.planos.get(cod).push({ ano, reee, lr, trecho, coleta, plano, pev, trechoPev });
    }
    M.extra = new Map();  // `${cod}|${ano}` -> {conv, sel, disp, taxa, passivo, nPassivos}
    for (const [cod, ano, conv, sel, disp, taxa, passivo, nPassivos] of d.sinir_mun || []) M.extra.set(`${cod}|${ano}`, { conv, sel, disp, taxa, passivo, nPassivos });
    if (S.city !== null && S.city >= M.n) S.city = null;
    const anosV = d.meta.anos_painel || d.meta.anos;
    $(".tag").textContent = `Logística reversa · SINIR ${anosV[0]}–${anosV[anosV.length - 1]}`;
    const todos = d.meta.anos_com_dados && d.meta.anos_com_dados.length ? d.meta.anos_com_dados : d.meta.anos;
    const comDados = todos.filter((a) => anosV.includes(a)).length ? todos.filter((a) => anosV.includes(a)) : anosV;
    // abre no ano inicial configurado (2023), ou no mais recente com algum dado
    if (!iniciado || !anosV.includes(S.ano)) S.ano = comDados.includes(d.meta.ano_inicial_painel) ? d.meta.ano_inicial_painel : comDados[comDados.length - 1];
    montarIndicadores();
    if (!iniciado) { init(); iniciado = true; } else { renderDados(); render(); }
    $$("#years button").forEach((b) => {
      const tem = comDados.includes(+b.dataset.ano);
      b.classList.toggle("sem-dados", !tem);
      b.title = tem ? "" : "Nenhum dado encontrado neste ano";
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
      const V = ANOS_V();
      const anos = V.map((a) => { const r = D.brasil_ano.find((x) => x.ano === a) || {};
        return `${a}: ${r.entidades || "sem relatório de pontos"}${r.planos_declarados ? " + planos municipais" : ""}`; });
      $("#banner-txt").textContent = `Dados reais publicados no SINIR (${anos.join(" · ")}). ` +
        "Pontos e massa vêm dos relatórios das entidades gestoras, por estado; o módulo Estados e Municípios não traz esses números, " +
        "então o painel mostra o que ele tem: planos municipais, coleta seletiva e plano de gestão. Anos com entidades diferentes não são comparáveis.";
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
    try {
      const r = await fetch(`api/atualizar${forcar ? "?forcar=1" : ""}`, { method: "POST" });
      if (r.status === 429) {  // atualizado há pouco (servidor na nuvem limita a frequência)
        const st = await r.json();
        pintarStatus("--warning", st.erro || "Os dados foram atualizados há pouco.");
        $("#st-btn").disabled = false;
        return;
      }
    } catch { /* o status mostra o que houve */ }
    ultimoEstado = "executando";
    checarStatus();
  }

  const anoIdx = () => D.meta.anos.indexOf(S.ano);
  const ufRow = (uf, ano = S.ano) => D.uf_ano.find((r) => r.uf === uf && r.ano === ano);
  const brRow = (ano = S.ano) => D.brasil_ano.find((r) => r.ano === ano);
  const ufsDaRegiao = () => (S.reg ? D.ufs.filter((u) => u.regiao === S.reg).map((u) => u.uf) : D.ufs.map((u) => u.uf));
  const naRegiao = (uf) => !S.reg || ufsDaRegiao().includes(uf);
  const soma = (rows, k) => { const v = rows.map((r) => r[k]).filter((x) => x !== null && x !== undefined); return v.length ? v.reduce((a, b) => a + b, 0) : null; };
  const pct = (n, d) => (n === null || !d ? null : Math.round((n / d) * 1000) / 10);
  function regRow(ano = S.ano) {  // soma das UFs da região, com os percentuais recalculados
    const rows = D.uf_ano.filter((r) => r.ano === ano && naRegiao(r.uf));
    const r = { ano };
    for (const k of ["pontos", "populacao", "municipios_atendidos", "toneladas", "pontos_exigidos", "obrigados", "planos_declarados",
      "planos_citam_reee", "planos_citam_pev", "planos_citam_lr", "municipios_passivo", "passivos", "coleta_seletiva_sim", "coleta_seletiva_resp", "plano_gestao_sim", "plano_gestao_resp"]) r[k] = soma(rows, k);
    r.entidades = [...new Set(rows.flatMap((x) => (x.entidades ? x.entidades.split(", ") : [])))].sort().join(", ") || null;
    r.dados_parciais = rows.some((x) => x.dados_parciais);
    r.pontos_100k = r.pontos === null ? null : (r.pontos / r.populacao) * 1e5;
    r.kg_hab = r.toneladas === null ? null : (r.toneladas * 1000) / r.populacao;
    r.cobertura_nominal = r.dados_parciais ? null : pct(r.pontos, r.pontos_exigidos);
    r.deficit_nominal = r.dados_parciais || r.pontos === null ? null : Math.max(0, r.pontos_exigidos - r.pontos);
    r.pct_planos_reee = pct(r.planos_citam_reee, r.planos_declarados);
    r.pct_planos_pev = pct(r.planos_citam_pev, r.planos_declarados);
    r.pct_planos_lr = pct(r.planos_citam_lr, r.planos_declarados);
    r.pct_coleta_seletiva = pct(r.coleta_seletiva_sim, r.coleta_seletiva_resp);
    r.pct_plano_gestao = pct(r.plano_gestao_sim, r.plano_gestao_resp);
    const ex = []; for (let i = 0; i < M.n; i++) { if (naRegiao(M.uf[i])) { const e = M.extra.get(`${M.cod[i]}|${ano}`); if (e) ex.push(e); } }
    r.custo_conv_hab = mediana(ex.map((e) => e.conv)); r.custo_sel_hab = mediana(ex.map((e) => e.sel));
    return r;
  }
  const scopeRow = (ano = S.ano) => (S.uf ? ufRow(S.uf, ano) : S.reg ? regRow(ano) : brRow(ano));
  const lugarNome = () => (S.uf ? ufNome(S.uf) : S.reg ? `Região ${S.reg}` : "Brasil");
  const entRot = (e) => (D.meta.entidade_linha && D.meta.entidade_linha[e] ? `${e} (${D.meta.entidade_linha[e]})` : e);
  const ufNome = (uf) => (D.ufs.find((u) => u.uf === uf) || {}).nome_uf || uf;

  /* ---------------- init ---------------- */
  function init() {
    $("#banner").hidden = D.meta.fonte !== "demo";
    // anos
    $("#years").innerHTML = ANOS_V().map((a) => `<button type="button" data-ano="${a}" aria-pressed="${a === S.ano}"${a === D.meta.ano_base ? ' title="Linha de base: único ano com ABREE e Green Eletron por estado"' : ""}>${a}${a === D.meta.ano_base ? ' <small>base</small>' : ""}</button>`).join("");
    $("#years").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      S.ano = +b.dataset.ano; $$("#years button").forEach((x) => x.setAttribute("aria-pressed", x === b)); montarIndicadores(); render();
    });
    // região (recorte do TCC: abre no Sudeste) e UF
    const sel = $("#f-uf"), reg = $("#f-reg");
    if (S.reg === null) S.reg = store.get("reee_regiao", D.meta.regiao_padrao || "");
    reg.value = S.reg;
    const preencherUFs = () => {
      sel.innerHTML = `<option value="">${S.reg ? "Todas da região" : "Brasil (todas)"}</option>`;
      D.ufs.filter((u) => naRegiao(u.uf)).sort((a, b) => a.nome_uf.localeCompare(b.nome_uf, "pt-BR"))
        .forEach((u) => sel.insertAdjacentHTML("beforeend", `<option value="${u.uf}">${u.nome_uf}</option>`));
      sel.value = S.uf;
    };
    preencherUFs();
    reg.addEventListener("change", () => { S.reg = reg.value; store.set("reee_regiao", S.reg); if (!naRegiao(S.uf)) S.uf = ""; preencherUFs(); render(); });
    sel.addEventListener("change", () => { S.uf = sel.value; render(); });
    $("#f-ind").addEventListener("change", (e) => { S.ind = e.target.value; S.indEscolhido = true; renderMap(); renderRank(); });
    $("#pm-camada").addEventListener("change", renderMapaMun);
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
    let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { renderMap(); renderMapaMun(); }, 150); });
  }

  function selectTab(id) {
    $$(".tab").forEach((t) => t.setAttribute("aria-selected", t.id === "tab-" + id));
    $$(".panel").forEach((p) => (p.hidden = p.id !== "panel-" + id));
    $("#filters").hidden = id === "dados";
    if (id === "cidadao") renderCidade();
  }

  function render() {
    renderKPIs(); renderMap(); renderRank(); renderCharts(); renderEntidades(); renderPlanos(); renderMapaMun(); renderCustos(); renderPeso(); renderAnalise();
    renderPrio(); renderAtencao(); renderCidade();
  }

  /* ---------------- planos municipais (texto livre declarado ao SINIR) ---------------- */
  function renderPlanos() {
    const card = $("#card-planos");
    const fonte = ANOS_V().map((a) => scopeRow(a)).filter(Boolean);
    const temDado = (D.planos_uf || []).length > 0;
    card.hidden = !temDado;
    if (!temDado) return;
    const anos = ANOS_V(), rows = anos.map((a) => fonte.find((r) => r.ano === a) || {});
    const o = baseOpts("municípios");
    mk("c-planos", { type: "bar", data: { labels: anos, datasets: [
      { label: "Declararam o plano", data: rows.map((r) => r.planos_declarados ?? null), backgroundColor: css("--axis"), borderRadius: 3, maxBarThickness: 30 },
      { label: "Preveem ecoponto/PEV", data: rows.map((r) => r.planos_citam_pev ?? null), backgroundColor: css("--series-2"), borderRadius: 3, maxBarThickness: 30 },
      { label: "Citam eletroeletrônicos", data: rows.map((r) => r.planos_citam_reee ?? null), backgroundColor: css("--series-1"), borderRadius: 3, maxBarThickness: 30 },
    ] }, options: o });
    const r = fonte.find((x) => x.ano === S.ano) || {};
    const lugar = S.uf ? ufNome(S.uf) : S.reg ? "na Região " + S.reg : "no Brasil";
    $("#planos-resumo").innerHTML = r.planos_declarados
      ? `<p><b class="num">${fmt(r.planos_citam_reee)}</b> de ${fmt(r.planos_declarados)} municípios que declararam o plano ${S.uf ? "em " + lugar : lugar} em ${S.ano} citam ações para eletroeletrônicos (<b>${fmt(r.pct_planos_reee, nf1)} %</b>).</p>
         ${r.planos_citam_pev !== undefined && r.planos_citam_pev !== null ? `<p><b class="num">${fmt(r.planos_citam_pev)}</b> preveem ecoponto, PEV ou ponto de entrega (${fmt(r.pct_planos_pev, nf1)} %): é a infraestrutura onde um ponto de recebimento de REEE pode funcionar.</p>` : ""}
         ${r.coleta_seletiva_resp ? `<p>Entre os que responderam ao diagnóstico, <b>${fmt(r.pct_coleta_seletiva, nf1)} %</b> têm coleta seletiva implantada e <b>${fmt(r.pct_plano_gestao, nf1)} %</b> têm plano de gestão de resíduos.</p>` : ""}
         <p class="muted">Ano de exercício: a declaração de ${S.ano} se refere, em geral, a ${S.ano - 1}. Classificação por palavras-chave em todos os campos de texto das planilhas municipais. Citar não prova que a ação foi executada; não citar não prova que ela não exista. Os trechos aparecem na ficha de cada cidade, na aba Cidadão.</p>`
      : `<p class="muted">Nenhum município ${S.uf ? "de " + lugar + " " : ""}declarou o plano ao SINIR em ${S.ano}.</p>`;
  }
  function planoHtml(i) {
    if (!(D.planos_mun || []).length) return "";
    const lista = (M.planos.get(M.cod[i]) || []).slice().sort((a, b) => b.ano - a.ano);
    const anosArq = [...new Set(D.planos_mun.map((p) => p[1]))].sort();
    const sem = anosArq.filter((a) => !lista.some((p) => p.ano === a));
    const sn = (v, rot) => (v === 1 ? `${rot}: sim` : v === 0 ? `${rot}: não` : "");
    const extra = (p) => [sn(p.coleta, "coleta seletiva"), sn(p.plano, "plano de gestão"), p.pev === 1 ? "prevê ecoponto/PEV" : ""].filter(Boolean).join(" · ")
      + (p.trechoPev ? ` — “${esc(p.trechoPev)}”` : "");
    const itens = lista.map((p) => (p.reee
      ? `<div class="item"><b>${p.ano} · cita eletroeletrônicos</b><span>“${esc(p.trecho)}”</span>`
      : `<div class="item"><b>${p.ano} · sem menção a eletroeletrônicos</b><span class="muted">O plano foi declarado${p.lr ? " e cita logística reversa de outros resíduos" : ""}, mas não fala de REEE.</span>`)
      + (extra(p) ? `<span class="small muted">${extra(p)}</span>` : "") + `</div>`).join("");
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
    const r = scopeRow() || {}, p = scopeRow(S.ano - 1), lugar = lugarNome();
    const quem = r.entidades ? `Informado por ${r.entidades}` : "Nenhuma entidade publicou dados deste recorte";
    const mesmo = p && p.entidades === r.entidades;  // variação só entre anos com as mesmas entidades
    // ano sem relatório: mostra o último dado disponível no recorte, marcado como tal (não é o valor do ano)
    const ultimo = (campo) => { for (let a = S.ano - 1; a >= D.meta.anos[0]; a--) { const x = scopeRow(a); if (x && x[campo] !== null && x[campo] !== undefined) return x; } return null; };
    const up = r.pontos === null || r.pontos === undefined ? ultimo("pontos") : null;
    const um = r.toneladas === null || r.toneladas === undefined ? ultimo("toneladas") : null;
    $("#k-pontos").innerHTML = up
      ? `<span class="label">Pontos de recebimento · ${lugar}</span>
        <div><span class="value muted-value">${fmt(up.pontos)}</span></div>
        <div class="sub"><b>Último dado: ${up.ano}</b> (${up.entidades || "entidades"}). Nenhuma entidade publicou ${S.ano} para este recorte.</div>`
      : `<span class="label">Pontos de recebimento · ${lugar}</span>
      <div><span class="value">${fmt(r.pontos)}</span></div>
      <div class="sub">${mesmo ? delta(r.pontos, p.pontos) : ""}</div>
      <div class="sub">${fmt(r.pontos_100k, nf2)} por 100 mil habitantes</div><div class="sub">${quem}</div>`;
    $("#k-massa").innerHTML = um
      ? `<span class="label">REEE coletado · ${lugar}</span>
        <div><span class="value muted-value">${fmt(um.toneladas)}</span><span class="unit">t</span></div>
        <div class="sub"><b>Último dado: ${um.ano}</b> (${um.entidades || "entidades"}). A massa de ${S.ano} não foi publicada${S.uf || S.reg ? " por estado" : ""}.</div>`
      : `<span class="label">REEE coletado · ${S.ano}</span>
      <div><span class="value">${fmt(r.toneladas)}</span><span class="unit">t</span></div>
      <div class="sub">${fmt(r.kg_hab, nf3)} kg/hab.</div>`;
    const meta = D.meta.metas_decreto[S.ano];
    $("#k-meta").innerHTML = `<span class="label">Municípios atendidos (informado)</span>
      <div><span class="value">${fmt(r.municipios_atendidos)}</span></div>
      ${!S.uf && !S.reg && meta ? `<span class="pill"><i class="dot" style="background:var(--muted)"></i>Meta do Decreto: ${fmt(meta.municipios)} municípios acima de 80 mil</span>` : ""}
      <div class="sub">Soma das entidades; um município atendido pelas duas conta duas vezes.</div>`;
    if ((r.pontos === null || r.pontos === undefined) && r.planos_declarados) {  // sem relatório de pontos: mostra o que existe
      $("#k-meta").innerHTML = `<span class="label">Planos municipais que citam REEE</span>
        <div><span class="value">${fmt(r.planos_citam_reee)}</span><span class="unit">de ${fmt(r.planos_declarados)}</span></div>
        <div class="sub">${fmt(r.pct_planos_reee, nf1)} % dos municípios que declararam o plano ao SINIR em ${S.ano}</div>`;
      $("#k-deficit").innerHTML = `<span class="label">Coleta seletiva implantada</span>
        <div><span class="value">${r.coleta_seletiva_resp ? fmt(r.pct_coleta_seletiva, nf1) : "–"}</span><span class="unit">%</span></div>
        <div class="sub">${r.coleta_seletiva_resp ? `${fmt(r.coleta_seletiva_sim)} de ${fmt(r.coleta_seletiva_resp)} municípios que responderam ao diagnóstico do SINIR` : `O SINIR não publicou o diagnóstico municipal de ${S.ano}`}</div>`;
      return;
    }
    const cob = r.cobertura_nominal;
    const cor = cob === null || cob === undefined ? "--muted" : cob >= 100 ? "--good" : cob >= 50 ? "--warning" : "--critical";
    $("#k-deficit").innerHTML = `<span class="label">Pontos informados ÷ exigidos</span>
      <div><span class="value">${cob === null || cob === undefined ? "–" : fmt(cob, nf1)}</span><span class="unit">%</span></div>
      <span class="pill"><i class="dot" style="background:var(${cor})"></i>${r.dados_parciais ? `Dados parciais: só ${r.entidades} divulgou ${S.ano}` : `${fmt(r.pontos)} de ${fmt(r.pontos_exigidos)} exigidos`}</span>
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
    // muitos estados empatados no mínimo (ex.: 0 % dos planos citam REEE) ficam no tom mais claro;
    // as faixas são calculadas só entre os demais, para o mapa não pintar "0" de azul médio
    const minV = d3.min(arr), acima = arr.filter((v) => v > minV);
    const qBase = acima.length >= 2 && acima.length < arr.length
      ? d3.scaleQuantile().domain(acima).range(ramp.slice(1)) : d3.scaleQuantile().domain(arr).range(ramp);
    const q = Object.assign((v) => (qBase.range().length === 4 && v <= minV ? ramp[0] : qBase(v)), { quantiles: () => qBase.quantiles() });
    const focus = S.uf ? feats.filter((f) => f.properties.uf === S.uf) : S.reg ? feats.filter((f) => naRegiao(f.properties.uf)) : feats;
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
    $("#map-title").textContent = `${IND[S.ind].label} · ${lugarNome()} · ${S.ano}`;
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
    const rows = D.uf_ano.filter((r) => r.ano === S.ano && r[S.ind] !== null && naRegiao(r.uf)).sort((a, b) => b[S.ind] - a[S.ind]);
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
  function mk(id, cfg) {
    charts[id]?.destroy();
    const cv = $("#" + id), box = cv.parentElement;
    box.querySelector(".chart-vazio")?.remove();
    const temValor = (cfg.data.datasets || []).some((ds) => (ds.data || []).some((v) => v !== null && v !== undefined && (typeof v !== "object" || (v.y !== null && v.y !== undefined))));
    cv.hidden = !temValor;
    if (!temValor) {  // em vez de eixos vazios com rótulos repetidos
      box.insertAdjacentHTML("beforeend", `<p class="chart-vazio">${cfg.vazio || "Nenhuma fonte publicou este dado para o recorte escolhido."}</p>`);
      charts[id] = null; return;
    }
    charts[id] = new Chart(cv, cfg);
  }

  function serieEntidade(campo) {
    // valores por entidade e ano no recorte atual (Brasil: totais nacionais; UF: tabela por UF)
    const porUF = S.uf || S.reg;
    const fonte = S.uf ? D.uf_entidade.filter((r) => r.uf === S.uf) : S.reg ? D.uf_entidade.filter((r) => naRegiao(r.uf)) : D.entidade_ano;
    const ents = [...new Set(fonte.map((r) => r.entidade))].sort();
    return ents.map((e) => ({ e: entRot(e), v: ANOS_V().map((a) => {
      const rs = fonte.filter((x) => x.entidade === e && x.ano === a);
      return porUF ? soma(rs, campo) : rs.length && rs[0][campo] !== null ? rs[0][campo] : null; }) }));
  }
  const tituloCard = (id, t, sub) => { const c = $("#" + id).closest(".card"); c.querySelector("h2").textContent = t; if (sub !== undefined) c.querySelector("header p").textContent = sub; };
  function renderChartsRel() {
    const anos = ANOS_V(), cores = [css("--series-1"), css("--series-2"), css("--series-3")];
    tituloCard("c-pontos", "Pontos de recebimento informados", "Por ano e entidade gestora; ano sem barra = sem relatório publicado");
    tituloCard("c-meta", "Municípios atendidos x meta", "Informado pelas entidades; meta de cidades atendidas do Decreto 10.240/2020 (Anexo II)");
    const empilhado = (id, campo, titulo, extra = []) => {
      const ds = serieEntidade(campo).map((s, k) => ({ type: "bar", label: s.e, data: s.v, backgroundColor: cores[k % 3], borderRadius: 3, maxBarThickness: 36, stack: "e" }));
      const o = baseOpts(titulo);
      o.scales.x.stacked = true; o.scales.y.stacked = true;
      mk(id, { data: { labels: anos, datasets: [...ds, ...extra] }, options: o,
        vazio: S.uf || S.reg ? "Só a ABREE informa massa por estado, e apenas em 2022. Escolha Brasil para ver a série nacional." : "Nenhuma entidade publicou este dado nos anos do painel." });
    };
    empilhado("c-pontos", "pontos", "pontos");
    const meta = anos.map((a) => (S.uf || S.reg ? null : D.meta.metas_decreto[a]?.municipios ?? null));
    empilhado("c-meta", "municipios_atendidos", "municípios", S.uf || S.reg ? [] : [{ type: "line", label: "Meta do Decreto", data: meta,
      borderColor: css("--ink-2"), borderDash: [5, 4], pointRadius: 4, pointBackgroundColor: css("--ink-2"), borderWidth: 2, stack: "meta" }]);
    empilhado("c-massa", "toneladas", "t");
    $("#massa-sub").textContent = S.uf ? "Toneladas por ano · só a ABREE informa massa por estado (2022)" : "Toneladas por ano e entidade · 2019–2021 só ABREE; 2023 só Green Eletron";
  }
  function renderCharts() {
    if (REL()) return renderChartsRel();
    tituloCard("c-pontos", "Pontos de recebimento ativos", "Por ano, recorte selecionado");
    tituloCard("c-meta", "Municípios obrigados com ponto x meta", "Meta de cidades atendidas do Decreto 10.240/2020 (Anexo II)");
    const anos = ANOS_V(), rows = anos.map((a) => scopeRow(a));
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
    else ds.push({ type: "line", label: "Meta do Decreto", data: meta, borderColor: s2, borderDash: [5, 4], pointRadius: 4, pointBackgroundColor: s2, pointBorderColor: surf, borderWidth: 2, spanGaps: false });
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
    const porUF = REL() && (S.uf || S.reg);
    const base = porUF ? D.uf_entidade.filter((r) => (S.uf ? r.uf === S.uf : naRegiao(r.uf))) : D.entidade_ano;
    $("#ent-sub").textContent = `${porUF ? lugarNome() : "Brasil"}, ${S.ano} · cada entidade atende principalmente uma linha de produto (seção 3.4)`;
    const ag = {};
    let anoE = S.ano;
    while (anoE > D.meta.anos[0] && !base.some((r) => r.ano === anoE && r.pontos !== null)) anoE--;
    if (anoE !== S.ano && base.some((r) => r.ano === anoE)) $("#ent-sub").textContent = `${porUF ? lugarNome() : "Brasil"} · último dado publicado: ${anoE} (nenhuma entidade publicou ${S.ano})`;
    base.filter((r) => r.ano === anoE && r.pontos !== null).forEach((r) => { ag[r.entidade] = (ag[r.entidade] || 0) + r.pontos; });
    const e = Object.entries(ag).map(([k, v]) => ({ k: entRot(k), v })).sort((a, b) => b.v - a.v);
    const t = D.tipo_ano.filter((r) => r.ano === S.ano).map((r) => ({ k: r.tipo, v: r.pontos })).sort((a, b) => b.v - a.v);
    const vazio = REL() ? `<p class="empty-state">Nenhuma entidade publicou pontos ${porUF ? "por estado " : ""}em ${S.ano}.</p>` : `<p class="empty-state">Esta fonte não detalha entidade gestora nem tipo de ponto.</p>`;
    if (e.length) hbars($("#entidades"), e, css("--series-1")); else $("#entidades").innerHTML = vazio;
    if (t.length) hbars($("#tipos"), t, css("--series-3")); else $("#tipos").innerHTML = "";
    $("#tipos-titulo").hidden = !t.length;
  }

  /* ---------------- mapa por município (pontos, passivos, planos) ---------------- */
  const mediana = (v) => { const a = v.filter((x) => x !== null && x !== undefined && !Number.isNaN(x)).sort((x, y) => x - y); if (!a.length) return null; const m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; };
  const noRecorte = (i) => (S.uf ? M.uf[i] === S.uf : naRegiao(M.uf[i]));
  function renderMapaMun() {
    const box = $("#mapa-mun"), camada = $("#pm-camada").value;
    const W = Math.max(300, box.clientWidth || 560), H = Math.round(Math.min(W * 0.85, 560));
    const feats = GEO.features.filter((f) => (S.uf ? f.properties.uf === S.uf : naRegiao(f.properties.uf)));
    const proj = d3.geoMercator().fitExtent([[8, 8], [W - 8, H - 8]], { type: "FeatureCollection", features: feats });
    const path = d3.geoPath(proj);
    let pts = [], cor = css("--series-1"), rot, nota;
    if (camada === "pev") {
      for (const r of D.mun_entidade) { const i = M.idx.get(r.cod_ibge); if (i !== undefined && noRecorte(i)) pts.push({ i, v: r.pontos, t: `${fmt(r.pontos)} PEV(s) da Green Eletron` }); }
      rot = "pontos de entrega"; nota = "Lista municipal do relatório de 2022 da Green Eletron (linha verde), o único que publica pontos por município. A ABREE publica só a contagem por estado. Use a camada como referência de onde já existe rede, não como retrato atual.";
    } else if (camada === "passivo") {
      cor = css("--critical");
      for (let i = 0; i < M.n; i++) { const e = M.extra.get(`${M.cod[i]}|${S.ano}`); if (e && e.passivo === 1 && noRecorte(i)) pts.push({ i, v: e.nPassivos || 1, t: `${fmt(e.nPassivos || 1)} passivo(s) declarado(s)` }); }
      rot = "municípios com passivo"; nota = `Lixões antigos e áreas degradadas declarados ao SINIR em ${S.ano}, na sede do município (o arquivo não traz coordenadas). Indicam onde o descarte inadequado já deixou marca.`;
    } else {
      const k = camada === "reee" ? "reee" : "pev";
      cor = camada === "reee" ? css("--series-1") : css("--series-2");
      for (const [cod, lista] of M.planos) { const p = lista.find((x) => x.ano === S.ano && x[k] === 1); const i = M.idx.get(cod); if (p && i !== undefined && noRecorte(i)) pts.push({ i, v: 1, t: camada === "reee" ? "plano cita eletroeletrônicos" : "plano prevê ecoponto/PEV" }); }
      rot = camada === "reee" ? "planos que citam REEE" : "planos com ecoponto/PEV"; nota = `Planos municipais declarados ao SINIR em ${S.ano}. Cada círculo é um município.`;
    }
    const r = d3.scaleSqrt().domain([0, d3.max(pts, (p) => p.v) || 1]).range([2.5, camada === "pev" ? 16 : 9]);
    box.innerHTML = "";
    const svg = d3.select(box).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", `Mapa por município: ${rot}`);
    svg.append("g").selectAll("path").data(feats).join("path").attr("d", path).attr("fill", css("--surface-2")).attr("stroke", css("--line")).attr("stroke-width", 0.8);
    svg.append("g").selectAll("circle").data(pts.sort((a, b) => b.v - a.v)).join("circle")
      .attr("cx", (p) => proj([M.lon[p.i], M.lat[p.i]])[0]).attr("cy", (p) => proj([M.lon[p.i], M.lat[p.i]])[1]).attr("r", (p) => r(p.v))
      .attr("fill", cor).attr("fill-opacity", 0.55).attr("stroke", cor).attr("stroke-width", 0.6)
      .on("mousemove", (e, p) => showTip(e, `<b>${M.nome[p.i]} – ${M.uf[p.i]}</b><br>${p.t}`)).on("mouseleave", hideTip)
      .on("click", (e, p) => { S.city = p.i; store.set("reee_city", p.i); selectTab("cidadao"); });
    $("#pm-sub").textContent = `${fmt(pts.length)} ${rot} · ${lugarNome()}${camada === "pev" ? "" : " · " + S.ano} · clique num círculo para abrir a ficha da cidade`;
    $("#pm-nota").textContent = nota;
  }

  /* ---------------- custos do manejo (SINIR) ---------------- */
  function renderCustos() {
    const card = $("#card-custos");
    card.hidden = !(D.sinir_mun || []).length;
    if (card.hidden) return;
    // ano sem planilha de custos (2023): usa o ano mais próximo que tem, avisando no subtítulo
    const anosCusto = [...new Set((D.sinir_mun || []).filter((r) => r[2] !== null).map((r) => r[1]))].sort();
    const anoC = anosCusto.includes(S.ano) ? S.ano : anosCusto.reduce((b, a) => (Math.abs(a - S.ano) < Math.abs(b - S.ano) ? a : b), anosCusto[0]);
    const doAno = [];
    for (let i = 0; i < M.n; i++) { const e = M.extra.get(`${M.cod[i]}|${anoC}`); if (e) doAno.push({ i, ...e }); }
    const rec = doAno.filter((x) => noRecorte(x.i));
    const conv = mediana(rec.map((x) => x.conv)), sel = mediana(rec.map((x) => x.sel));
    const taxaResp = rec.filter((x) => x.taxa !== null), taxa = taxaResp.length ? (taxaResp.filter((x) => x.taxa === 1).length / taxaResp.length) * 100 : null;
    const nConv = rec.filter((x) => x.conv !== null).length;
    $("#custos-sub").textContent = `Mediana por habitante · ${lugarNome()} · ${anoC}${anoC !== S.ano ? ` (o SINIR não publicou custos de ${S.ano})` : ""} · ${fmt(nConv)} municípios informaram custo`;
    const kp = (v, rot) => `<div><b>${v}</b><span>${rot}</span></div>`;
    $("#custos-kpis").innerHTML = kp(conv === null ? "–" : "R$ " + fmt(conv, nf1), "coleta convencional /hab./ano")
      + kp(sel === null ? "–" : "R$ " + fmt(sel, nf1), "coleta seletiva /hab./ano") + kp(taxa === null ? "–" : fmt(taxa, nf1) + " %", "cobram taxa de resíduos");
    const ufs = S.uf ? [S.uf] : ufsDaRegiao();
    const linhas = ufs.map((uf) => { const m = doAno.filter((x) => M.uf[x.i] === uf); return { uf, conv: mediana(m.map((x) => x.conv)), sel: mediana(m.map((x) => x.sel)) }; })
      .filter((l) => l.conv !== null || l.sel !== null).sort((a, b) => (b.conv ?? 0) - (a.conv ?? 0));
    const o = baseOpts("R$ por habitante por ano");
    mk("c-custos", { type: "bar", vazio: `O SINIR não publicou custos municipais em ${S.ano} (o arquivo de 2023 não traz a planilha de custos).`,
      data: { labels: linhas.map((l) => l.uf), datasets: [
        { label: "Coleta convencional", data: linhas.map((l) => l.conv), backgroundColor: css("--axis"), borderRadius: 3, maxBarThickness: 22 },
        { label: "Coleta seletiva", data: linhas.map((l) => l.sel), backgroundColor: css("--series-2"), borderRadius: 3, maxBarThickness: 22 },
      ] }, options: o });
  }

  /* ---------------- meta em peso (seção 3.5) ---------------- */
  function renderPeso() {
    const card = $("#card-peso");
    const base = D.meta.base_peso_2018_t || {}, div = D.meta.coleta_divulgada_t || [];
    card.hidden = !REL() || !Object.keys(base).length;
    if (card.hidden) return;
    const linhas = [];
    for (const a of ANOS_V()) {
      const m = D.meta.metas_decreto[a];
      if (!m) continue;
      for (const e of [...new Set([...Object.keys(base), ...D.entidade_ano.filter((r) => r.ano === a).map((r) => r.entidade)])].sort()) {
        const metaT = base[e] ? (base[e] * m.percentual_peso) / 100 : null;
        const col = (D.entidade_ano.find((r) => r.entidade === e && r.ano === a) || {}).toneladas ?? null;
        const txt = div.find((d) => d.entidade === e && d.ano === a);
        let sit, cor = "--muted";
        if (col !== null && metaT) { const p = (col / metaT) * 100; sit = p >= 100 ? `Atingiu (${fmt(p, nf1)} %)` : `Abaixo (${fmt(p, nf1)} %)`; cor = p >= 100 ? "--good" : "--critical"; }
        else if (txt) sit = txt.texto;
        else sit = metaT ? "Massa não divulgada" : "Base de 2018 não divulgada";
        linhas.push(`<tr><td class="mono">${a}</td><td class="r mono">${m.percentual_peso} %</td><td>${e}</td><td class="r">${metaT ? fmt(metaT) : "–"}</td>
          <td class="r">${col !== null ? fmt(col) : "–"}</td><td style="white-space:normal"><span class="pill"><i class="dot" style="background:var(${cor})"></i>${sit}</span>${txt && col === null ? `<div class="small muted">${txt.fonte}</div>` : ""}</td></tr>`);
      }
    }
    $("#peso tbody").innerHTML = linhas.join("") || `<tr><td colspan="6" class="empty-state">Sem dados.</td></tr>`;
    $("#peso-nota").textContent = "A meta é calculada sobre o peso que as empresas de cada sistema colocaram no mercado em 2018, valor que não é público. " +
      "Para a Green Eletron, a base foi estimada pela meta de 2024 divulgada (12 % = 8.066,17 t). A ABREE não divulga a base, por isso o percentual não pode ser calculado. " +
      "Como só há massa por entidade, este quadro vale para o Brasil inteiro, sem recorte por região.";
  }

  /* ---------------- análise quantitativa (seção 3.6) ---------------- */
  function renderAnalise() {
    const a = D.meta.analise_quantitativa, card = $("#card-analise");
    card.hidden = !a;
    if (!a) return;
    const dentro = a.pontos.filter((p) => naRegiao(p.uf)), fora = a.pontos.filter((p) => !naRegiao(p.uf));
    const xs = a.pontos.map((p) => p.x), x0 = 0, x1 = Math.max(...xs) * 1.05;
    const o = baseOpts("kg por habitante");
    o.scales.x = { ...o.scales.y, type: "linear", min: 0, title: { display: true, text: "pontos por 100 mil habitantes", color: css("--ink-2") },
      ticks: { ...(o.scales.y.ticks || {}), callback: (v) => fmt(v, nf1) } };
    o.scales.y = { ...o.scales.y, ticks: { ...(o.scales.y.ticks || {}), callback: (v) => fmt(v, nf2) } };
    o.plugins.tooltip = { callbacks: { label: (c) => c.raw.uf ? `${ufNome(c.raw.uf)}: ${fmt(c.raw.x, nf2)} pontos/100 mil · ${fmt(c.raw.y, nf3)} kg/hab.` : "Tendência linear" } };
    mk("c-analise", { type: "scatter", data: { datasets: [
      { label: S.reg ? `UFs da Região ${S.reg}` : "UFs", data: dentro, backgroundColor: css("--series-1"), pointRadius: 5 },
      ...(fora.length ? [{ label: "Demais UFs", data: fora, backgroundColor: css("--axis"), pointRadius: 4 }] : []),
      { type: "line", label: "Tendência (mínimos quadrados)", data: [{ x: x0, y: a.intercepto + a.inclinacao * x0 }, { x: x1, y: a.intercepto + a.inclinacao * x1 }],
        borderColor: css("--ink-2"), borderDash: [5, 4], pointRadius: 0, borderWidth: 2 },
    ] }, options: o });
    $("#analise-sub").textContent = `Uma bolinha por UF · ${a.entidades}, ${a.ano} (único ano com pontos e massa por estado nos relatórios)`;
    const forca = Math.abs(a.pearson) >= 0.7 ? "forte" : Math.abs(a.pearson) >= 0.4 ? "moderada" : "fraca";
    $("#analise-txt").innerHTML = `Correlação de Pearson <b class="mono">r = ${fmt(a.pearson, nf2)}</b>, de Spearman <b class="mono">ρ = ${fmt(a.spearman, nf2)}</b> e regressão linear com <b class="mono">R² = ${fmt(a.r2, nf2)}</b> (n = ${a.n} UFs). ` +
      `Há associação positiva ${forca}: estados com mais pontos por habitante tendem a recolher mais REEE por habitante. ` +
      `<span class="muted">É uma análise descritiva de um único ano: não prova causa e não substitui a série histórica, que os relatórios ainda não permitem montar.</span>`;
  }

  /* ---------------- municípios que pedem atenção (SINIR 2023–2025) ---------------- */
  function renderAtencao() {
    const card = $("#card-atencao");
    card.hidden = !REL() || !(D.planos_mun || []).length;
    if (card.hidden) return;
    const green = new Set(D.mun_entidade.map((r) => r.cod_ibge));
    const lim = D.meta.limiar_populacional, hpp = D.meta.hab_por_ponto_decreto;
    const sn = (v) => (v === true || v === 1 ? "sim" : v === false || v === 0 ? "<b>não</b>" : "–");
    const rows = [];
    for (let i = 0; i < M.n; i++) {
      if (M.pop[i] <= lim || (S.uf ? M.uf[i] !== S.uf : !naRegiao(M.uf[i]))) continue;
      const p = (M.planos.get(M.cod[i]) || []).find((x) => x.ano === S.ano);
      const declarou = !!p, pev = green.has(M.cod[i]);
      const sinais = (!declarou) + (declarou && !p.reee) + (declarou && p.coleta === 0) + (declarou && p.pev === 0) + (!pev);
      rows.push({ i, p, declarou, pev, sinais });
    }
    rows.sort((a, b) => b.sinais - a.sinais || M.pop[b.i] - M.pop[a.i]);
    $("#atencao-sub").textContent = `${fmt(rows.length)} municípios-alvo em ${lugarNome()} (aproximação: mais de 80 mil habitantes) · declarações ao SINIR de ${S.ano}`;
    $("#atencao tbody").innerHTML = rows.slice(0, 40).map((r, k) => `<tr><td class="mono">${k + 1}</td><td>${M.nome[r.i]}</td><td>${M.uf[r.i]}</td>
      <td class="r">${fmt(M.pop[r.i])}</td><td class="r">${Math.ceil(M.pop[r.i] / hpp)}</td>
      <td>${sn(r.declarou)}</td><td>${r.declarou ? sn(!!r.p.reee) : "–"}</td><td>${r.declarou ? sn(r.p.coleta) : "–"}</td><td>${r.declarou ? sn(r.p.pev) : "–"}</td><td>${sn(r.pev)}</td>
      <td class="r mono">${r.sinais}</td></tr>`).join("") || `<tr><td colspan="11" class="empty-state">Nenhum município-alvo neste recorte.</td></tr>`;
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
    // a comparação com a regra do Decreto só vale com todas as entidades: usa o último ano completo até o ano escolhido
    const doAno = (a) => D.uf_ano.filter((r) => r.ano === a && r.pontos !== null && !r.dados_parciais && (S.uf ? r.uf === S.uf : naRegiao(r.uf)));
    let anoP = S.ano, rows = doAno(anoP);
    while (!rows.length && anoP > D.meta.anos[0]) rows = doAno(--anoP);
    rows.sort((a, b) => (b.deficit_nominal ?? -1) - (a.deficit_nominal ?? -1));
    const ents = D.brasil_ano.find((r) => r.ano === anoP)?.entidades || "sem relatório";
    $("#prio-sub").textContent = (anoP !== S.ano ? `Em ${S.ano} não há relatório de todas as entidades por estado; para comparar com a regra do Decreto, a tabela usa o último ano completo (${anoP}, ${ents}). ` : `${S.ano}, ${ents}. `) +
      "Estados ordenados pelos pontos que faltam para a regra do Decreto. Para os municípios, veja \"Municípios que pedem atenção\".";
    $("#prio thead").innerHTML = `<tr><th>#</th><th>UF</th><th class="r">População</th><th class="r">Municípios &gt; 80 mil</th><th class="r">Pontos exigidos</th><th class="r">Pontos informados</th><th class="r">Faltam</th><th class="r">Informados ÷ exigidos</th><th>Situação</th></tr>`;
    $("#prio tbody").innerHTML = rows.length ? rows.map((r, i) => {
      const c = r.cobertura_nominal, sem = c === null || c === undefined;
      const cor = sem ? "--muted" : c >= 100 ? "--good" : c >= 50 ? "--warning" : "--critical";
      const txt = sem ? "Dados parciais" : c >= 100 ? "Atende em número" : c >= 50 ? "Abaixo do exigido" : "Muito abaixo";
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
      ${(() => { const e = M.extra.get(`${M.cod[i]}|${S.ano}`); if (!e) return ""; const it = [];
        if (e.conv !== null) it.push(`coleta convencional: <b>R$ ${fmt(e.conv, nf2)}</b> por habitante/ano`);
        if (e.sel !== null) it.push(`coleta seletiva: <b>R$ ${fmt(e.sel, nf2)}</b> por habitante/ano`);
        if (e.taxa !== null) it.push(e.taxa === 1 ? "cobra taxa de resíduos" : "não cobra taxa de resíduos");
        if (e.passivo === 1) it.push(`<b>${fmt(e.nPassivos || 1)}</b> passivo(s) ambiental(is) declarado(s), como lixão antigo ou área degradada`);
        return it.length ? `<div><span class="label">Declarado ao SINIR em ${S.ano}</span><div class="list"><div class="item">${it.map((x) => `<span>${x}</span>`).join("")}</div></div></div>` : ""; })()}
      <div class="status-line"><i class="dot" style="background:var(--muted)"></i><p>Em ${S.ano}, ${u.entidades ? `as entidades (${u.entidades}) informaram <b>${fmt(u.pontos)}</b> pontos em ${ufNome(uf)}${u.dados_parciais ? " (dados parciais: nem todas as entidades divulgaram este ano)." : `, ${fmt(u.cobertura_nominal, nf1)} % do que a regra exige no estado.`}` : `nenhuma entidade publicou dados de ${ufNome(uf)}.`} </p></div>
      <div><span class="label">Encontre o ponto de recebimento mais próximo</span>
        <div class="row-btns">${Object.entries(D.meta.localizadores || {}).map(([e, u]) => `<a class="btn" href="${u}" target="_blank" rel="noopener">${entRot(e)} ↗</a>`).join("")}</div>
        <p class="small muted">O SINIR não publica os endereços dos pontos; cada entidade mantém o próprio localizador (busca por CEP ou cidade). Se não encontrar, peça à prefeitura pela Lei de Acesso à Informação.</p></div>
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
      const c = { tipo: $("#p-tipo").value, municipio: mun, local: $("#p-local").value.trim(), descricao: desc, data: new Date().toISOString() };
      const guardar = (msg) => { const l = lista(); l.push(c); store.set("reee_contrib", l); t.textContent = msg; $("#p-desc").value = ""; $("#p-local").value = ""; draw(); };
      if (!apiOk) { guardar("Registrada neste navegador (esta versão do painel não tem servidor). Use \"Copiar como CSV\" para enviar ao município."); return; }
      fetch("api/contribuicao", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(c) })
        .then(async (r) => { const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.erro || "falha no envio"); guardar("Contribuição enviada. Ela aparece em Dados abertos › contribuicoes.csv para o gestor responder."); })
        .catch((err) => { t.textContent = `Não foi possível enviar: ${err.message}`; });
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
      ["data/abertos/planos_municipais_reee.csv", "Planos municipais: cita eletroeletrônicos, coleta seletiva e plano de gestão, com o trecho de origem"],
      ["data/abertos/contribuicoes.csv", "e-Participação: contribuições enviadas pelo painel (sem dados pessoais)"],
      ["data/abertos/linhas_relacionadas_reee_sinir.csv", "ETL do SINIR: todas as linhas que citam eletroeletrônicos ou logística reversa, com arquivo de origem e classificação"],
      ["data/abertos/inventario_arquivos_sinir.csv", "ETL do SINIR: inventário de arquivos e abas de cada ano"],
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
      planos_declaracoes: "Planos municipais lidos (2023–2025, município × ano)", planos_citam_reee: "Planos que citam eletroeletrônicos (2023–2025)",
      custo_conv_descartados: "Custos de coleta convencional descartados (zero ou acima de R$ 1.000/hab.)",
      custo_sel_descartados: "Custos de coleta seletiva descartados (zero ou acima de R$ 1.000/hab.)",
      custo_disp_descartados: "Custos de disposição final descartados (zero ou acima de R$ 1.000/hab.)",
      extras_municipio_ano: "Registros de custo e passivo (município × ano)",
      abas_lidas: "Abas de planilha lidas", abas_com_codigo_ibge: "Abas com código IBGE (municipais)",
      anos_com_campo_pontos: "Anos com nº de pontos de REEE", anos_com_campo_toneladas: "Anos com massa de REEE",
      anos_com_campo_possui: "Anos com 'possui ponto de REEE'", declaracoes_municipio_ano: "Declarações município × ano",
      etl_sinir: "ETL do SINIR (linhas candidatas por ano de exercício)", nota_sinir: "Observação", aviso: "Aviso", coleta_falhas: "Falhas na coleta", relatorios_validados: "Relatórios",
    };
    const corr = D.qualidade.relatorio_municipios_nome_corrigido || [];
    $("#qualidade tbody").innerHTML = (corr.length ? `<tr><td style="white-space:normal">Nomes corrigidos no casamento com o IBGE</td><td class="r mono">${corr.length}</td></tr><tr><td colspan="2" class="small muted" style="white-space:normal">${corr.join("; ")}</td></tr>` : "") + Object.entries(D.qualidade).filter(([, v]) => !Array.isArray(v))
      .map(([k, v]) => typeof v === "number"
        ? `<tr><td style="white-space:normal">${rot[k] || k}</td><td class="r mono">${fmt(v)}</td></tr>`
        // texto longo (observações, resumo do ETL) ocupa a linha inteira, alinhado à esquerda
        : `<tr><td colspan="2" style="white-space:normal"><span class="qual-rot">${rot[k] || k}</span><span class="small muted">${esc(k === "fonte" ? (ROTULO_FONTE[v] || v) : v)}</span></td></tr>`).join("");
    $("#funil tbody").innerHTML = (D.meta.funil || []).map((f) => `<tr><td class="mono">${f.ano}</td><td class="r">${fmt(f.municipios)}</td>
      <td class="r">${fmt(f.declararam)} <span class="muted small">(${fmt((f.declararam / f.municipios) * 100, nf1)} %)</span></td>
      <td class="r">${fmt(f.citam_logistica_reversa)}</td><td class="r">${fmt(f.preveem_ecoponto_pev)}</td><td class="r"><b>${fmt(f.citam_reee)}</b></td></tr>`).join("")
      || `<tr><td colspan="6" class="empty-state">Sem planilhas do SINIR.</td></tr>`;
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

  /* ---------------- tema claro/escuro ---------------- */
  // Sem escolha salva, segue o sistema; o botão grava a escolha. Mudar data-theme já redesenha
  // mapas e gráficos (MutationObserver em init), porque as cores vêm das variáveis CSS.
  (function initTema() {
    const btn = $("#theme-btn"), mq = matchMedia("(prefers-color-scheme: dark)");
    const ICONE = {
      dark: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" fill="currentColor"/></svg>',
      light: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.5" fill="currentColor" stroke="none"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/></svg>',
    };
    const atual = () => document.documentElement.dataset.theme || (mq.matches ? "dark" : "light");
    const pintar = () => {
      const t = atual(), outro = t === "dark" ? "claro" : "escuro";
      btn.innerHTML = ICONE[t === "dark" ? "light" : "dark"];  // mostra o tema para o qual o clique leva
      btn.setAttribute("aria-label", `Mudar para o tema ${outro}`);
      btn.title = `Mudar para o tema ${outro}`;
    };
    btn.addEventListener("click", () => {
      const novo = atual() === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = novo;
      store.set("reee.tema", novo);
      pintar();
    });
    mq.addEventListener?.("change", pintar);
    pintar();
  })();

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
