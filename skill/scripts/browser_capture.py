from __future__ import annotations

import re

SANITIZER_JS = r"""
  const normalizeKey = key => String(key)
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/[^a-z0-9]+/gi, "_")
    .toLowerCase();
  const sensitiveKey = new RegExp(
    "(?:^|_)(?:email|e_mail|phone|mobile|first_name|last_name|firstname|lastname|" +
    "address|postal|postcode|zip|user_id|customer_id|password|passcode|secret|" +
    "token|authorization|cookie|card_number|credit_card|cvv|security_code|iban|" +
    "session_id|client_secret|api_key|date_of_birth|birthdate|dob)(?:$|_)",
    "i"
  );
  const sanitize = (value, key = "", depth = 0) => {
    if (sensitiveKey.test(normalizeKey(key))) return "[redacted]";
    if (depth > 6) return "[depth-limited]";
    if (value === null || ["string", "number", "boolean"].includes(typeof value)) return value;
    if (Array.isArray(value)) return value.slice(0, 25).map(item => sanitize(item, key, depth + 1));
    if (typeof value === "object") {
      const result = {};
      Object.entries(value).slice(0, 50).forEach(([childKey, child]) => {
        result[childKey] = sanitize(child, childKey, depth + 1);
      });
      return result;
    }
    return `[${typeof value}]`;
  };
""".strip()


def data_layer_capture_init_script(callback_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", callback_name):
        raise ValueError(f"Invalid browser callback name: {callback_name}")
    return (
        "(() => {\n"
        f"{SANITIZER_JS}\n"
        "  window.dataLayer = Array.isArray(window.dataLayer) ? window.dataLayer : [];\n"
        "  const originalPush = window.dataLayer.push.bind(window.dataLayer);\n"
        "  window.dataLayer.push = (...items) => {\n"
        "    items.forEach(item => {\n"
        f"      try {{ window.{callback_name}(sanitize(item)); }} catch (_) {{}}\n"
        "    });\n"
        "    return originalPush(...items);\n"
        "  };\n"
        "})();"
    )


def measurement_evidence_script() -> str:
    return (
        "() => {\n"
        f"{SANITIZER_JS}\n"
        "  const dataLayer = Array.isArray(window.dataLayer) ? window.dataLayer : [];\n"
        "  const pushes = dataLayer.slice(-100).map(value => sanitize(value));\n"
        "  const resources = performance.getEntriesByType('resource').map(entry => entry.name || '');\n"
        "  const corpus = [document.documentElement.innerHTML, ...resources].join('\\n');\n"
        "  const unique = values => [...new Set(values)];\n"
        "  return {\n"
        "    data_layer_present: Array.isArray(window.dataLayer),\n"
        "    data_layer_push_count: dataLayer.length,\n"
        "    data_layer_pushes: pushes,\n"
        "    gtm_container_ids: unique(corpus.match(/GTM-[A-Z0-9]+/gi) || []).sort(),\n"
        "    google_tag_ids: unique(corpus.match(/GT-[A-Z0-9]+/gi) || []).sort(),\n"
        "    ga4_measurement_ids: unique(corpus.match(/G-[A-Z0-9]{6,}/gi) || []).sort()\n"
        "  };\n"
        "}"
    )
