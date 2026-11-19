import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans-arabic/400.css';
// No fixture values are shown until the shared Fact chip family is available.
const message = document.createElement('p');
const arabic = new URLSearchParams(location.search).get('lang') === 'ar';
document.documentElement.lang = arabic ? 'ar' : 'en';
document.documentElement.dir = arabic ? 'rtl' : 'ltr';
message.textContent = arabic
  ? 'العرض متوقف حتى تتوفر مكونات الحقائق المشتركة.'
  : 'Chart display is blocked until the shared Fact components are available.';
document.body.append(message);

document.body.style.fontFamily = arabic
  ? 'IBM Plex Sans Arabic'
  : 'IBM Plex Sans';
document.body.style.lineHeight = '1.6';
document.body.style.letterSpacing = '0';
