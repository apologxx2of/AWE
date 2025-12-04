// WikiParser.js
const WikiParser = (function() {
  // --- util ---
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function isAbsoluteUrl(u) {
    return /^[a-zA-Z]+:\/\//.test(u) || u.startsWith('//');
  }

  // tokens for protection
  let tokenIdx = 0;
  function makeToken(prefix) { return `@@${prefix}_${tokenIdx++}@@`; }

  // MAIN parse function
  function parse(wikitext, options = {}) {
    tokenIdx = 0;
    options = Object.assign({
      linkResolver: slug => `/goto/${encodeURIComponent(slug)}`,
      templateResolver: null, // function(name, params) => html|string|null
      maxTableCols: 50,
      sanitize: true // we recommend you run final html through DOMPurify if in browser
    }, options);

    // 1) protect <nowiki>...</nowiki> and <pre>...</pre> and <code>...</code>
    const protectedMap = {};
    function protectBlock(regex, key) {
      wikitext = wikitext.replace(regex, (m, inner) => {
        const tok = makeToken(key);
        protectedMap[tok] = inner;
        return tok;
      });
    }
    // <nowiki>.*?</nowiki> (dotall)
    protectBlock(/<nowiki>([\s\S]*?)<\/nowiki>/gi, 'NOWIKI');
    protectBlock(/<pre>([\s\S]*?)<\/pre>/gi, 'PRE');
    protectBlock(/<code>([\s\S]*?)<\/code>/gi, 'CODE');

    // 2) handle <ref> ... </ref> collecting footnotes
    const refs = [];
    wikitext = wikitext.replace(/<ref(?: [^>]*)?>([\s\S]*?)<\/ref>/gi, (m, inner) => {
      const id = refs.length + 1;
      refs.push(inner);
      return `<sup class="mw-ref"><a href="#ref-${id}" id="ref-link-${id}">[${id}]</a></sup>`;
    });

    // 3) split into lines and process block-level constructs (tables, lists, headings)
    const lines = wikitext.replace(/\r\n/g, '\n').split('\n');

    const out = [];
    let i = 0;

    // helpers for lists
    function flushList(stack, outArr) {
      while (stack.length) {
        const tag = stack.pop();
        outArr.push(`</${tag}>`);
      }
    }

    while (i < lines.length) {
      let line = lines[i];

      // Tables: start with "{|"
      if (/^\{\|/.test(line)) {
        // gather table lines until "|}"
        const tableLines = [];
        while (i < lines.length && !/^\|\}/.test(lines[i])) {
          tableLines.push(lines[i]);
          i++;
        }
        // consume the closing "|}" if present
        if (i < lines.length && /^\|\}/.test(lines[i])) i++;
        out.push(renderTable(tableLines.join('\n'), options));
        continue;
      }

      // Headings: == Heading ==
      const hMatch = line.match(/^(={1,6})\s*(.*?)\s*\1\s*$/);
      if (hMatch) {
        const level = hMatch[1].length;
        out.push(`<h${level}>${inlineParse(hMatch[2], options)}</h${level}>`);
        i++;
        continue;
      }

      // Horizontal rule ----
      if (/^----\s*$/.test(line)) {
        out.push('<hr/>');
        i++;
        continue;
      }

      // Preformatted block: lines starting with a space -> <pre>
      if (/^ /.test(line)) {
        const block = [];
        while (i < lines.length && (/^ /.test(lines[i]) || lines[i] === '')) {
          block.push(lines[i].replace(/^ /, ''));
          i++;
        }
        const content = escapeHtml(block.join('\n'));
        out.push(`<pre>${content}</pre>`);
        continue;
      }

      // Lists and definition lists
      if (/^[\*\#\:\;]+/.test(line)) {
        // We'll parse consecutive lines of lists into nested tags
        const stack = []; // tags stack
        const html = [];
        while (i < lines.length && /^[\*\#\:\;]+/.test(lines[i])) {
          const m = lines[i].match(/^([\*\#\:\;]+)\s*(.*)$/);
          const markers = m[1];
          const text = m[2];
          // compute required stack for markers
          const needed = [];
          for (const ch of markers) {
            if (ch === '*') needed.push('ul');
            else if (ch === '#') needed.push('ol');
            else if (ch === ':') needed.push('dd');
            else if (ch === ';') needed.push('dt');
          }
          // reconcile stack -> needed
          let common = 0;
          while (common < stack.length && common < needed.length && stack[common] === needed[common]) common++;
          // close extras
          for (let k = stack.length - 1; k >= common; k--) {
            html.push(`</${stack[k]}>`);
          }
          // open new
          for (let k = common; k < needed.length; k++) {
            const tag = needed[k];
            html.push(`<${tag}>`);
          }
          // replace stack
          stack.length = 0;
          for (const t of needed) stack.push(t);

          // emit item content: if dd/dt then wrap in <div> else in <li>
          if (markers.endsWith(':') || markers.endsWith(';')) {
            html.push(inlineParse(text, options));
          } else {
            html.push(`<li>${inlineParse(text, options)}</li>`);
          }

          i++;
        }
        // flush remaining
        while (stack.length) {
          html.push(`</${stack.pop()}>`);
        }
        out.push(html.join('\n'));
        continue;
      }

      // Empty line => paragraph break
      if (/^\s*$/.test(line)) {
        out.push('');
        i++;
        continue;
      }

      // Normal paragraph line(s) - group until blank or block start
      const paraLines = [];
      while (i < lines.length && lines[i] !== '' && !/^(={1,6}\s*.*\s*=+|^\{\||^\|\}|^----|^[\*\#\:\;]|^ )/.test(lines[i])) {
        paraLines.push(lines[i]);
        i++;
      }
      const para = paraLines.join(' ');
      out.push(`<p>${inlineParse(para, options)}</p>`);
    }

    // 4) After building, insert references list if there's a <references/> token — but we earlier replaced <ref> tags inline.
    let html = out.join('\n');
    // Replace <references/> tag if present in original (but we removed refs already)
    if (/\<references\s*\/\>/.test(wikitext) || /\{\{reflist\}\}/i.test(wikitext)) {
      const refsHtml = refs.length ? `<ol class="references">${refs.map((r, idx) => `<li id="ref-${idx+1}">${inlineParse(r, options)}</li>`).join('')}</ol>` : '<p class="references-empty">Sem referências.</p>';
      // naive replace
      html = html.replace(/\<references\s*\/\>/gi, refsHtml);
      html = html.replace(/\{\{reflist\}\}/gi, refsHtml);
    }

    // restore protected tokens
    for (const tok in protectedMap) {
      html = html.replace(new RegExp(tok.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), escapeHtml(protectedMap[tok]));
    }

    // optionally sanitize (recommend to use DOMPurify externally)
    if (options.sanitize && typeof window !== 'undefined' && window.DOMPurify) {
      html = window.DOMPurify.sanitize(html, {ADD_TAGS: ['iframe'], ADD_ATTR: ['loading']});
    }

    return html;
  }

  // --- inline parser: bold/italic, links, templates, urls ---
  function inlineParse(text, options) {
    if (!text) return '';

    // Protect pipe inside templates? We'll process templates first ({{...}})
    text = processTemplates(text, options);

    // protect <nowiki/> tokens already handled

    // External links: [http://example.com label]
    text = text.replace(/\[([^\s\]]+)\s+([^\]]+)\]/g, (m, url, lbl) => {
      const href = escapeHtml(url);
      const label = inlineParse(lbl, options);
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    });

    // Bare external URL in brackets [http://...] without label
    text = text.replace(/\[([^\s\]]+)\]/g, (m, url) => {
      const href = escapeHtml(url);
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">${href}</a>`;
    });

    // Internal links [[Page|label]] or [[Page#section|lbl]] or [[Namespace:Page|lbl]]
    text = text.replace(/\[\[([^\]]+)\]\]/g, (m, inside) => {
      // split by pipe
      const parts = inside.split('|');
      const target = parts[0].trim();
      const label = parts.slice(1).join('|').trim() || parts[0].trim();

      // if starts with File: or Image: treat as image link (basic)
      if (/^(File|Image|Arquivo|Ficheiro):/i.test(target)) {
        // try to get filename after colon
        const fn = target.split(':').slice(1).join(':').trim();
        const url = options.imageResolver ? options.imageResolver(fn) : `/uploads/${encodeURIComponent(fn)}`;
        return `<img src="${escapeHtml(url)}" alt="${escapeHtml(label)}" />`;
      }

      // anchor support
      const anchorSplit = target.split('#');
      const page = anchorSplit[0].trim();
      const anchor = anchorSplit[1] ? '#'+encodeURIComponent(anchorSplit[1].trim()) : '';

      const href = options.linkResolver ? options.linkResolver(page) + anchor : `/goto/${encodeURIComponent(page)}${anchor}`;
      return `<a href="${escapeHtml(href)}">${inlineParse(label, options)}</a>`;
    });

    // Bold/italic: order matters -> ''''' (bold+italic) -> ''' -> ''
    // handle ''''' (bold+italic)
    text = text.replace(/'''''(.*?)'''''/g, (m, inner) => `<strong><em>${inlineParse(inner, options)}</em></strong>`);
    // bold
    text = text.replace(/'''(.*?)'''/g, (m, inner) => `<strong>${inlineParse(inner, options)}</strong>`);
    // italic
    text = text.replace(/''(.*?)''/g, (m, inner) => `<em>${inlineParse(inner, options)}</em>`);

    // Templates already processed but might remain
    // Now anonymous templates or leftover {{...}} -> render as text
    text = text.replace(/\{\{([^\}]+)\}\}/g, (m, inner) => {
      return escapeHtml(`{{${inner}}}`);
    });

    // html-escape any leftover '<' '>'? We assume higher-level cleaned
    return text;
  }

  // --- Template processor: supports simple {{name|p1|p2=val}} with recursion ---
  function processTemplates(text, options) {
    // recursive regex parsing using stack
    const stack = [];
    const results = [];
    let out = '';
    for (let i = 0; i < text.length; i++) {
      if (text[i] === '{' && text[i+1] === '{') {
        stack.push({start: i});
        i++; // skip second {
      } else if (text[i] === '}' && text[i+1] === '}' && stack.length) {
        const top = stack.pop();
        const end = i+1;
        if (stack.length === 0) {
          // outermost template from top.start to end
          const before = text.slice(0, top.start);
          const tplRaw = text.slice(top.start+2, end-1);
          const after = text.slice(end+1);
          // process inner templates recursively
          const evaled = evalTemplate(tplRaw, options);
          text = before + evaled + after;
          i = before.length + evaled.length - 1;
        } else {
          i++; // just closing inner
        }
      }
    }
    return text;
  }

  function evalTemplate(tplRaw, options) {
    // split by | but not within nested braces - simple split works because nested were resolved earlier
    const parts = tplRaw.split('|');
    const name = parts[0].trim();
    const params = {};
    const positional = [];
    for (let i = 1; i < parts.length; i++) {
      const p = parts[i];
      const eq = p.indexOf('=');
      if (eq >= 0) {
        const k = p.slice(0, eq).trim();
        const v = p.slice(eq+1).trim();
        params[k] = v;
      } else {
        positional.push(p.trim());
      }
    }

    // call resolver if provided
    if (typeof options.templateResolver === 'function') {
      try {
        const r = options.templateResolver(name, {positional, params});
        if (r != null) return String(r);
      } catch (e) {
        console.error('templateResolver error', e);
      }
    }

    // default simple rendering: show a box with params
    let html = `<span class="tpl">${escapeHtml(name)}`;
    if (positional.length || Object.keys(params).length) {
      html += ': ';
      const bits = [];
      for (let i=0;i<positional.length;i++) bits.push(escapeHtml(positional[i]));
      for (const k in params) bits.push(`${escapeHtml(k)}=${escapeHtml(params[k])}`);
      html += bits.join(', ');
    }
    html += '</span>';
    return html;
  }

  // --- Table renderer: basic support for rows and cells ---
  function renderTable(text, options) {
    // text includes starting "{|" lines etc. We'll parse simply
    const lines = text.split('\n');
    const attrsLine = lines[0]; // like "{| class="wikitable"
    const rows = [];
    let currentRow = null;

    for (let i=1;i<lines.length;i++) {
      const L = lines[i];
      if (/^\|-\s*(.*)/.test(L)) {
        // new row
        const m = L.match(/^\|-\s*(.*)/);
        currentRow = {cells: [], rawAttrs: m && m[1] ? m[1].trim() : ''};
        rows.push(currentRow);
      } else if (/^\!/.test(L)) {
        // header cell (could be multiple separated by !!)
        const cells = L.replace(/^\!/, '').split('!!');
        for (const c of cells) currentRow.cells.push({header:true, text:c.trim()});
      } else if (/^\|/.test(L)) {
        // normal cell; multiple || possible
        const cells = L.replace(/^\|/, '').split('||');
        for (const c of cells) currentRow.cells.push({header:false, text:c.trim()});
      } else {
        // continuation or caption line etc -> ignore or append
        if (rows.length === 0) {
          // maybe caption: starts with "|+" or "!"?
        } else {
          // append to last cell text
          const last = currentRow && currentRow.cells[currentRow.cells.length-1];
          if (last) last.text += ' ' + L.trim();
        }
      }
    }

    // render HTML table
    const cls = (attrsLine.match(/class\s*=\s*"(.*?)"/) || [null,''])[1] || '';
    const html = ['<table' + (cls ? ` class="${escapeHtml(cls)}"` : '') + '>'];
    for (const r of rows) {
      html.push('<tr>');
      for (const c of (r.cells || [])) {
        const tag = c.header ? 'th' : 'td';
        html.push(`<${tag}>${inlineParse(c.text, options)}</${tag}>`);
      }
      html.push('</tr>');
    }
    html.push('</table>');
    return html.join('\n');
  }

  // export
  return {
    parse,
    inlineParse,
    processTemplates,
    // helper to register simple template resolvers (optional)
    buildParserWith: function(customOptions) {
      return {
        parse: (w) => parse(w, customOptions),
        inlineParse: (t) => inlineParse(t, customOptions)
      };
    }
  };
})();