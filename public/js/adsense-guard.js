(function () {
  var KEY = 'pa_ads_guard';
  var LIMIT = 3;
  var WINDOW_MS = 24 * 60 * 60 * 1000;
  var DEBOUNCE_MS = 1500;
  var ARM_MS = 15000;
  var FOCUS_GRACE_MS = 800;
  var CLIENT = 'ca-pub-8094444885520451';
  var AD_ZONE = '.adsbygoogle, .ad-unit, .ad-slot';
  var AD_FRAME_RE = /googlesyndication|doubleclick|aswift|google_ads_iframe|googleads/i;

  var armedUntil = 0;
  var pendingLeaveAt = 0;
  var lastCountAt = 0;
  var blockActive = false;
  var scriptRequested = false;
  var observer = null;

  function isElement(node) {
    return Boolean(node && node.nodeType === 1);
  }

  function readState() {
    var now = Date.now();
    try {
      var data = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (
        !data ||
        typeof data.startedAt !== 'number' ||
        typeof data.clicks !== 'number' ||
        now - data.startedAt >= WINDOW_MS
      ) {
        data = { startedAt: now, clicks: 0 };
        localStorage.setItem(KEY, JSON.stringify(data));
      }
      blockActive = data.clicks >= LIMIT;
      return data;
    } catch (error) {
      blockActive = false;
      return { startedAt: now, clicks: 0 };
    }
  }

  function writeState(data) {
    try {
      localStorage.setItem(KEY, JSON.stringify(data));
    } catch (error) {}
    blockActive = data.clicks >= LIMIT;
  }

  function refreshBlock() {
    readState();
    return blockActive;
  }

  function isAdZone(node) {
    return isElement(node) && typeof node.closest === 'function' && Boolean(node.closest(AD_ZONE));
  }

  function isAdFrame(node) {
    if (!isElement(node) || node.tagName !== 'IFRAME') return false;
    var hint =
      (node.getAttribute('src') || '') +
      ' ' +
      (node.id || '') +
      ' ' +
      (node.name || '') +
      ' ' +
      (typeof node.className === 'string' ? node.className : '');
    if (AD_FRAME_RE.test(hint)) return true;
    return isAdZone(node);
  }

  function isAdScript(node) {
    if (!isElement(node) || node.tagName !== 'SCRIPT') return false;
    return /adsbygoogle\.js|googlesyndication|doubleclick/i.test(node.getAttribute('src') || '');
  }

  function fromAd(event) {
    return isAdZone(event.target) || isAdFrame(event.target);
  }

  // Ad iframes are cross-origin, so the parent stops receiving mouse events
  // once the pointer is over the frame. Hold the arm and do not clear it on blur.
  function arm(fromAdFocus) {
    var now = Date.now();
    var until = now + ARM_MS;
    if (until > armedUntil) armedUntil = until;
    if (!fromAdFocus || !pendingLeaveAt || now - pendingLeaveAt > FOCUS_GRACE_MS) return;
    pendingLeaveAt = 0;
    commitClick(now);
  }

  function commitClick(now) {
    if (blockActive) return;
    if (now - lastCountAt < DEBOUNCE_MS) return;
    lastCountAt = now;
    armedUntil = now + ARM_MS;
    var data = readState();
    if (data.clicks >= LIMIT) {
      blockActive = true;
      wipe();
      return;
    }
    data.clicks += 1;
    writeState(data);
    if (blockActive) wipe();
  }

  function noteLeave() {
    refreshBlock();
    if (blockActive) {
      wipe();
      return;
    }
    var now = Date.now();
    if (now >= armedUntil) {
      pendingLeaveAt = now;
      return;
    }
    pendingLeaveAt = 0;
    commitClick(now);
  }

  function neutralizePush() {
    var blockPush = function () {
      return 0;
    };
    var queue = window.adsbygoogle || [];
    queue.push = blockPush;
    try {
      Object.defineProperty(window, 'adsbygoogle', {
        configurable: true,
        enumerable: true,
        get: function () {
          return queue;
        },
        set: function (value) {
          queue = value && typeof value === 'object' ? value : [];
          queue.push = blockPush;
        },
      });
    } catch (error) {
      window.adsbygoogle = queue;
    }
  }

  function purgeNode(node) {
    if (!isElement(node)) return;
    if (node.matches && node.matches(AD_ZONE)) {
      node.remove();
      return;
    }
    if (isAdFrame(node) || isAdScript(node)) {
      node.remove();
      return;
    }
    if (!node.querySelectorAll) return;
    node.querySelectorAll(AD_ZONE + ', iframe, script').forEach(function (child) {
      if (child.matches && child.matches(AD_ZONE)) child.remove();
      else if (isAdFrame(child) || isAdScript(child)) child.remove();
    });
  }

  function wipe() {
    blockActive = true;
    neutralizePush();
    document.querySelectorAll(AD_ZONE).forEach(function (node) {
      node.remove();
    });
    document.querySelectorAll('iframe').forEach(function (node) {
      if (isAdFrame(node)) node.remove();
    });
    document.querySelectorAll('script[src]').forEach(function (node) {
      if (isAdScript(node)) node.remove();
    });
    scriptRequested = false;
  }

  function ensureObserver() {
    if (observer || !document.documentElement) return;
    observer = new MutationObserver(function (mutations) {
      if (!blockActive) return;
      if (!refreshBlock()) return;
      for (var i = 0; i < mutations.length; i++) {
        var mutation = mutations[i];
        if (mutation.type === 'attributes') {
          purgeNode(mutation.target);
          continue;
        }
        var nodes = mutation.addedNodes;
        for (var j = 0; j < nodes.length; j++) purgeNode(nodes[j]);
      }
    });
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['src', 'id', 'name'],
    });
  }

  function loadScript() {
    if (refreshBlock() || scriptRequested) return;
    if (document.querySelector('script[src*="adsbygoogle.js"]')) {
      scriptRequested = true;
      return;
    }
    scriptRequested = true;
    var script = document.createElement('script');
    script.async = true;
    script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + CLIENT;
    script.crossOrigin = 'anonymous';
    document.head.appendChild(script);
  }

  function onPointer(event) {
    if (blockActive || !fromAd(event)) return;
    arm(false);
  }

  function onFocus(event) {
    if (blockActive || !fromAd(event)) return;
    arm(true);
  }

  document.addEventListener('pointerover', onPointer, true);
  document.addEventListener('mouseover', onPointer, true);
  document.addEventListener('pointerdown', onPointer, true);
  document.addEventListener('touchstart', onPointer, { capture: true, passive: true });
  document.addEventListener('focusin', onFocus, true);
  document.addEventListener('focus', onFocus, true);
  window.addEventListener('blur', noteLeave);
  window.addEventListener('pagehide', noteLeave);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') {
      noteLeave();
      return;
    }
    if (refreshBlock()) wipe();
  });
  window.addEventListener('pageshow', function () {
    if (refreshBlock()) wipe();
  });
  window.addEventListener('storage', function (event) {
    if (event.key !== KEY) return;
    if (refreshBlock()) wipe();
  });

  window.__paAds = {
    allowed: function () {
      return !refreshBlock();
    },
    mount: function (host) {
      if (!isElement(host)) return;
      if (refreshBlock()) {
        host.remove();
        return;
      }
      if (host.querySelector('ins.adsbygoogle')) return;

      var ins = document.createElement('ins');
      var width = host.getAttribute('data-ad-width');
      var height = host.getAttribute('data-ad-height');
      ins.className = 'adsbygoogle';
      ins.setAttribute('data-ad-client', CLIENT);
      ins.setAttribute('data-ad-slot', host.getAttribute('data-ad-slot') || '');
      if (width && height) {
        ins.style.display = 'inline-block';
        ins.style.width = width + 'px';
        ins.style.height = height + 'px';
      } else {
        ins.style.display = 'block';
        ins.setAttribute('data-ad-format', 'auto');
        ins.setAttribute('data-full-width-responsive', 'true');
      }
      host.replaceChildren(ins);
      if (refreshBlock()) {
        wipe();
        return;
      }
      loadScript();
      if (refreshBlock()) {
        wipe();
        return;
      }
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    },
  };

  ensureObserver();
  if (refreshBlock()) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wipe);
    else wipe();
  }
})();
