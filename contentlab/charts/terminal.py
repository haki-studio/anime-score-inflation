"""
contentlab.charts.terminal  --  Reusable interactive line chart, styled to the
Haki Studios site design language (Neue Metana display + Helvetica Neue body,
dark editorial palette, green accent, tight tracking).

  * build_fragment(...)   -> self-contained HTML fragment (Chart.js) to inline
                             anywhere on a page.
  * build_standalone(...) -> the fragment in a minimal transparent-bg document.
  * srcdoc_iframe(html)   -> wrap a standalone doc in <iframe srcdoc> for pasting
                             into editors that strip <script> (e.g. Shopify blog).

The fragment is namespaced by `chart_id` (scoped CSS + unique canvas), loads
Chart.js from CDN once even with several charts on a page, renders when ready,
and - when it lives inside an iframe - resizes that iframe to its own content
height (no inner scrollbar), which also survives a host that strips iframe sizing
attributes.

datasets: list of dicts
  {label, data: [..], color: "#rrggbb", axis: "left"|"right",
   dashed: bool=False, hidden: bool=False}
"""
import json

CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"

# Site design tokens (dark mode; mirrors sections/haki-article.liquid .is-dark)
FONT_BODY = "'Helvetica Neue', Helvetica, Arial, sans-serif"
FONT_DISPLAY = "'Neue Metana', 'Helvetica Neue', Helvetica, Arial, sans-serif"

# Chart titles use FONT_DISPLAY ('Neue Metana'), but when the chart is embedded as
# an <iframe srcdoc> the iframe is a SEPARATE document and does NOT inherit the
# host theme's @font-face rules - so the title silently falls back to Helvetica
# Neue. Set FONT_DISPLAY_URL to the theme's live Neue Metana woff2 URL and the
# fragment emits its own @font-face so the title renders correctly inside the
# iframe. Leave it empty to keep the fallback (no broken/blocked font request).
FONT_DISPLAY_URL = ""           # e.g. "https://hakistop.myshopify.com/cdn/fonts/neue_metana/...woff2?..."
FONT_DISPLAY_FAMILY = "Neue Metana"
FONT_DISPLAY_WEIGHT = 700
FONT_DISPLAY_FORMAT = "woff2"
T = {
    "ink": "#f1f1f1", "muted": "#9a9a9a", "line": "rgba(255,255,255,0.16)",
    "grid": "rgba(255,255,255,0.10)", "surface": "rgba(255,255,255,0.03)",
    "green": "#46c98b", "tooltip": "#161616",
}
# default data palette: brand green leads, then a warm sand and a cool periwinkle
PALETTE = ["#46c98b", "#d9a441", "#7c9ce6"]


def _font_face():
    """@font-face for the display font, so it resolves inside an iframe srcdoc.

    Empty when FONT_DISPLAY_URL is unset, so no font request is made (the title
    falls back to Helvetica Neue rather than blocking on a missing URL).
    """
    if not FONT_DISPLAY_URL:
        return ""
    return (f"@font-face{{font-family:'{FONT_DISPLAY_FAMILY}';"
            f"src:url('{FONT_DISPLAY_URL}') format('{FONT_DISPLAY_FORMAT}');"
            f"font-weight:{FONT_DISPLAY_WEIGHT};font-style:normal;font-display:swap}}\n")


def _css(cid):
    return _font_face() + f"""
#{cid}{{color:{T['ink']};font-family:{FONT_BODY};letter-spacing:-0.03em;
  max-width:860px;margin:0 auto;padding:4px 0 2px}}
#{cid} *{{box-sizing:border-box}}
#{cid} .hkc-head{{display:flex;justify-content:space-between;align-items:baseline;
  border-bottom:1px solid {T['line']};padding-bottom:12px;margin-bottom:14px;flex-wrap:wrap;gap:8px}}
#{cid} .hkc-title{{font-family:{FONT_DISPLAY};font-weight:700;text-transform:uppercase;
  letter-spacing:-0.025em;font-size:17px;line-height:1.1;color:{T['ink']}}}
#{cid} .hkc-sub,#{cid} .hkc-src{{font-size:11.5px;color:{T['muted']};text-transform:uppercase;letter-spacing:-0.02em}}
#{cid} .hkc-sub{{margin-top:4px}}
#{cid} .hkc-stats{{display:flex;gap:26px;margin:2px 0 16px;flex-wrap:wrap}}
#{cid} .hkc-stat{{display:flex;flex-direction:column}}
#{cid} .hkc-stat .k{{font-size:10.5px;color:{T['muted']};text-transform:uppercase;letter-spacing:-0.01em}}
#{cid} .hkc-stat .v{{font-size:21px;font-weight:700;margin-top:3px;color:{T['ink']}}}
#{cid} .hkc-up{{color:{T['green']}}} #{cid} .hkc-down{{color:#e08a7a}}
#{cid} .hkc-toggles{{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}}
#{cid} .hkc-toggles button{{background:transparent;color:{T['muted']};border:1px solid {T['line']};
  padding:5px 11px;font:inherit;font-size:11px;text-transform:uppercase;letter-spacing:-0.02em;
  border-radius:2px;cursor:pointer}}
#{cid} .hkc-toggles button.on{{color:{T['ink']};border-color:{T['green']}}}
#{cid} .hkc-box{{background:{T['surface']};border:1px solid {T['line']};border-radius:4px;padding:12px}}
#{cid} canvas{{width:100% !important}}
#{cid} .hkc-foot,#{cid} .hkc-cap{{font-size:12px;color:{T['muted']};margin-top:12px;line-height:1.5}}
#{cid} .hkc-cap a{{color:{T['green']}}}
""".strip()


def _toggles_html(datasets):
    btns = "".join(
        f'<button data-set="{i}" class="{"" if d.get("hidden") else "on"}">{d["label"]}</button>'
        for i, d in enumerate(datasets)
    )
    return f'<div class="hkc-toggles">{btns}</div>'


def _stats_html(stat_cards):
    if not stat_cards:
        return ""
    cards = "".join(
        f'<div class="hkc-stat"><span class="k">{c["k"]}</span>'
        f'<span class="v{(" " + c["cls"]) if c.get("cls") else ""}">{c["v"]}</span></div>'
        for c in stat_cards
    )
    return f'<div class="hkc-stats">{cards}</div>'


def build_fragment(chart_id, labels, datasets, *, title, subtitle="", source="",
                   left_axis_title="", right_axis_title="", y_left=None, y_right=None,
                   stat_cards=None, footnote="", caption_html="", height=340):
    payload = {
        "labels": labels, "datasets": datasets,
        "leftTitle": left_axis_title, "rightTitle": right_axis_title,
        "yLeft": y_left, "yRight": y_right,
        "hasRight": any(d.get("axis") == "right" for d in datasets),
        "t": T,
    }
    init = """
(function(){
  var P = %(payload)s, ID = "%(cid)s", T = P.t;
  function fit(){
    try{ if(window.frameElement){
      var h = Math.ceil(document.body.scrollHeight);
      if(h){ window.frameElement.style.height = h + "px";
             window.frameElement.setAttribute("scrolling","no"); }
    } }catch(e){}
  }
  function draw(){
    var el = document.getElementById(ID + "-canvas");
    if (!el || el.dataset.drawn) return; el.dataset.drawn = "1";
    Chart.defaults.font.family = "Helvetica Neue, Helvetica, Arial, sans-serif";
    Chart.defaults.color = T.muted;
    var sets = P.datasets.map(function(d){
      return {label:d.label, data:d.data, borderColor:d.color, backgroundColor:d.color,
        yAxisID:(d.axis==="right"?"yR":"yL"), tension:.25, borderWidth:2, pointRadius:2,
        pointHoverRadius:5, spanGaps:true, borderDash:(d.dashed?[4,3]:[]), hidden:!!d.hidden};
    });
    var scales = {
      x:{grid:{color:T.grid},border:{color:T.line},ticks:{color:T.muted,maxRotation:0,autoSkip:true,maxTicksLimit:12}},
      yL:{position:"left",grid:{color:T.grid},border:{color:T.line},ticks:{color:T.muted},
          title:{display:!!P.leftTitle,text:P.leftTitle,color:T.muted}}
    };
    if (P.yLeft){ scales.yL.min = P.yLeft[0]; scales.yL.max = P.yLeft[1]; }
    if (P.hasRight){
      var rc = P.datasets.filter(function(d){return d.axis==="right";})[0];
      var rcol = rc ? rc.color : T.muted;
      scales.yR = {position:"right",grid:{drawOnChartArea:false},border:{color:T.line},ticks:{color:rcol},
        title:{display:!!P.rightTitle,text:P.rightTitle,color:rcol}};
      if (P.yRight){ scales.yR.min = P.yRight[0]; scales.yR.max = P.yRight[1]; }
    }
    var chart = new Chart(el.getContext("2d"), {
      type:"line", data:{labels:P.labels, datasets:sets},
      options:{responsive:true, interaction:{mode:"index",intersect:false},
        plugins:{legend:{display:false},
          tooltip:{backgroundColor:T.tooltip,borderColor:T.line,borderWidth:1,
            titleColor:T.ink,bodyColor:T.muted,padding:10,cornerRadius:3}},
        scales:scales, onResize:fit}
    });
    var root = document.getElementById(ID);
    root.querySelectorAll(".hkc-toggles button").forEach(function(b){
      b.addEventListener("click", function(){
        var i = +b.dataset.set, ds = chart.data.datasets[i];
        ds.hidden = !ds.hidden; b.classList.toggle("on", !ds.hidden);
        if (P.hasRight && chart.options.scales.yR){
          chart.options.scales.yR.display = P.datasets.some(function(d,j){
            return d.axis==="right" && !chart.data.datasets[j].hidden; });
        }
        chart.update(); fit();
      });
    });
    fit(); setTimeout(fit,80); setTimeout(fit,400);
    window.addEventListener("resize", fit);
    if (window.ResizeObserver){ new ResizeObserver(fit).observe(document.body); }
  }
  function ready(){
    if (window.Chart) return draw();
    if (!window.__hkChartLoading){
      window.__hkChartLoading = true;
      var s = document.createElement("script"); s.src = "%(cdn)s"; document.head.appendChild(s);
    }
    var n=0, t=setInterval(function(){ if(window.Chart){clearInterval(t);draw();} else if(++n>200){clearInterval(t);} },50);
  }
  if (document.readyState !== "loading") ready();
  else document.addEventListener("DOMContentLoaded", ready);
})();
""" % {"payload": json.dumps(payload), "cid": chart_id, "cdn": CDN}

    cap = f'<div class="hkc-cap">{caption_html}</div>' if caption_html else ""
    foot = f'<div class="hkc-foot">{footnote}</div>' if footnote else ""
    return f"""<div id="{chart_id}">
<style>{_css(chart_id)}</style>
<div class="hkc-head">
  <div><div class="hkc-title">{title}</div><div class="hkc-sub">{subtitle}</div></div>
  <div class="hkc-src">{source}</div>
</div>
{_stats_html(stat_cards)}
{_toggles_html(datasets)}
<div class="hkc-box"><canvas id="{chart_id}-canvas" height="{height}"></canvas></div>
{foot}
{cap}
<script>{init}</script>
</div>"""


def srcdoc_iframe(standalone_html, *, height=420, title="Chart", max_width=880):
    """Wrap a standalone chart doc in an <iframe srcdoc="...">.

    For editors that strip <script> on save: the script lives inside the iframe's
    own document, encoded as an attribute value, so the host-page sanitizer only
    sees an <iframe>. We escape < > & " so the host doc has no literal "<script"
    substring (defeats naive regex sanitizers); the browser entity-decodes srcdoc
    before parsing it as the iframe document. The chart resizes the iframe to its
    content from inside, so the `height` here is only an initial value.
    """
    esc = (standalone_html.replace("&", "&amp;").replace("<", "&lt;")
           .replace(">", "&gt;").replace('"', "&quot;"))
    return (
        f'<iframe srcdoc="{esc}" width="100%" height="{height}" scrolling="no" '
        f'style="border:0;width:100%;max-width:{max_width}px;display:block;margin:0 auto;background:transparent" '
        f'loading="lazy" title="{title}"></iframe>'
    )


def build_standalone(chart_id, labels, datasets, **kwargs):
    frag = build_fragment(chart_id, labels, datasets, **kwargs)
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{kwargs.get("title", "Chart")}</title>\n'
        "<style>html,body{margin:0;padding:0;background:transparent}</style>\n"
        f"</head>\n<body>\n{frag}\n</body>\n</html>\n"
    )
