// 한국어 조사 고르기: 글 속의 '이(가)', '을(를)', '은(는)', '와(과)', '(으)로' 를 바로 앞 글자의 받침에 맞게 바꾼다.
//   josa('풍차이(가) 완성됐어요') → '풍차가 완성됐어요',  josa('오두막(으)로') → '오두막으로'

const FORMS = {
  '이(가)': ['가', '이'], '을(를)': ['를', '을'], '은(는)': ['는', '은'], '와(과)': ['와', '과'], '(으)로': ['로', '으로'],
  '가(이)': ['가', '이'], '를(을)': ['를', '을'], '는(은)': ['는', '은'], '과(와)': ['와', '과'],
};
const DIGIT = [1, 8, 0, 1, 0, 0, 1, 8, 8, 0];   // 0영 1일 2이 3삼 4사 5오 6육 7칠 8팔 9구 (0 받침 없음, 8 ㄹ 받침, 1 그 밖의 받침)

// 받침: 0 없음, 8 ㄹ, 그 밖의 수 = 받침 있음, null = 글자가 아님(괄호·따옴표 등은 건너뛴다)
function tail(c) {
  if (c >= 0xac00 && c <= 0xd7a3) return (c - 0xac00) % 28;
  if (c >= 48 && c <= 57) return DIGIT[c - 48];
  if ((c >= 65 && c <= 90) || (c >= 97 && c <= 122)) return 0;
  return null;
}

export function josa(s) {
  if (typeof s !== 'string' || s.indexOf('(') < 0) return s;
  return s.replace(/이\(가\)|을\(를\)|은\(는\)|와\(과\)|가\(이\)|를\(을\)|는\(은\)|과\(와\)|\(으\)로/g, (m, off, str) => {
    let t = 0;
    for (let i = off - 1, k = 0; i >= 0 && k < 6; i--, k++) {
      const c = str.charCodeAt(i);
      // 괄호 속 덧붙임은 건너뛰고 괄호 앞 낱말에 맞춘다: '민준(77세)이(가)' → '민준(77세)이'
      if (c === 41) { let d = 1; while (i > 0 && d) { i--; const h = str.charCodeAt(i); if (h === 41) d++; else if (h === 40) d--; } k = -1; continue; }
      const v = tail(c); if (v !== null) { t = v; break; }
    }
    const f = FORMS[m];
    if (m === '(으)로') return t && t !== 8 ? f[1] : f[0];
    return t ? f[1] : f[0];
  });
}
