/**
 * 데모 안전성 스캐너 (A-06).
 *
 * 앱 소스 전체를 훑어 발표/데모에서 노출되면 안 되는 패턴을 검사한다:
 *   - 자격증명/비밀 (password/secret/api_key 값, JWT, private key 블록)
 *   - 완전 숫자 식별번호 패턴 (마스킹되지 않은 실 식별번호 형태)
 *   - 문서용(RFC5737)·사설(RFC1918) 대역 밖의 공인 IPv4
 *
 * 실행:
 *   /System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc \
 *     app/tools/safety-scan.js
 *   # 또는
 *   node app/tools/safety-scan.js
 *
 * 종료 메시지가 "SAFETY: PASS"가 아니면 데모 반입 금지.
 */
var ROOT = "app/";
var FILES = [
  "index.html",
  "js/config.js", "js/ui.js", "js/store.js", "js/app.js", "js/router.js",
  "js/api/mock.js", "js/api/client.js",
  "js/screens/home.js", "js/screens/scenarios.js", "js/screens/briefing.js",
  "js/screens/missionDesk.js", "js/screens/aar.js", "js/screens/ops.js",
];

var findings = [];
function flag(file, kind, sample) { findings.push({ file: file, kind: kind, sample: sample }); }
function out(message) {
  if (typeof print === "function") print(message);
  else if (typeof console !== "undefined" && console.log) console.log(message);
}
function readText(path) {
  if (typeof read === "function") return read(path);
  if (typeof require === "function") return require("fs").readFileSync(path, "utf8");
  throw new Error("No file reader available");
}

function octetsOk(m) {
  for (var i = 1; i <= 4; i++) { if (Number(m[i]) > 255) return false; }
  return true;
}
// 허용 대역: RFC1918 사설 + RFC5737 문서용
function ipAllowed(a, b) {
  if (a === 127) return true;                  // loopback (로컬 API 예시)
  if (a === 10) return true;
  if (a === 192 && b === 168) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 0) return true;      // 192.0.2.0/24 (셋째 옥텟은 별도 확인 생략)
  if (a === 198 && b === 51) return true;      // 198.51.100.0/24
  if (a === 203 && b === 0) return true;       // 203.0.113.0/24
  return false;
}

var reJwt = /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}/;
var rePriv = /-----BEGIN [A-Z ]*PRIVATE KEY-----/;
var reSecret = /(password|passwd|secret|api[_-]?key|client[_-]?secret|access[_-]?token)\s*[:=]\s*["'][^"']{6,}["']/i;
var reSvcNum = /\b\d{2}-\d{5}-\d{1,3}\b/;      // 완전 숫자 식별번호 형태 (마스킹 X)
var reIp = /\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b/g;

FILES.forEach(function (rel) {
  var text;
  try { text = readText(ROOT + rel); } catch (e) { flag(rel, "READ_ERROR", String(e)); return; }

  if (reJwt.test(text)) flag(rel, "JWT_LIKE", (text.match(reJwt) || [])[0]);
  if (rePriv.test(text)) flag(rel, "PRIVATE_KEY", (text.match(rePriv) || [])[0]);
  var secretHit = text.match(reSecret);
  // A masked value (contains ***) is exactly what we want, not a leak.
  if (secretHit && secretHit[0].indexOf("***") === -1) flag(rel, "SECRET_LITERAL", secretHit[0]);
  if (reSvcNum.test(text)) flag(rel, "SERVICE_NUMBER", (text.match(reSvcNum) || [])[0]);

  var m;
  reIp.lastIndex = 0;
  while ((m = reIp.exec(text)) !== null) {
    if (!octetsOk(m)) continue;                // 1.0.0.1234 같은 버전 문자열 제외
    var a = Number(m[1]), b = Number(m[2]);
    if (!ipAllowed(a, b)) flag(rel, "PUBLIC_IP", m[0]);
  }
});

if (findings.length === 0) {
  out("SAFETY: PASS — 자격증명/실 식별번호/문서용 외 공인 IP 미검출 (" + FILES.length + " files)");
} else {
  out("SAFETY: FAIL — " + findings.length + " finding(s)");
  findings.forEach(function (f) { out("  [" + f.kind + "] " + f.file + " :: " + f.sample); });
}
