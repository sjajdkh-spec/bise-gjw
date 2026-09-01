import re, hashlib, httpx
from bs4 import BeautifulSoup

class ProviderError(Exception): pass
class ResultNotAvailable(Exception): pass
class CaptchaRequired(Exception): pass
class AccessBlocked(Exception): pass

class BiseGujranwalaProvider:
    def __init__(self, official_url, fallback_url='', timeout=20):
        self.official_url=official_url.rstrip('/')
        self.fallback_url=(fallback_url or '').strip()
        self.timeout=timeout
        self.headers={'User-Agent':'Mozilla/5.0 (compatible; BISE-GRW-Result-Bot/1.1)','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Accept-Language':'en-US,en;q=0.9'}

    async def fetch(self, roll_number, class_name, year):
        roll=str(roll_number).strip(); cls=str(class_name).lower().replace('class','').strip(); year=int(year)
        if not re.fullmatch(r'\\d{3,10}',roll): raise ProviderError('Invalid roll number format.')
        if cls not in {'9th','10th','11th','12th'}: raise ProviderError('Class must be 9th, 10th, 11th, or 12th.')
        last=None
        urls=[self.official_url]
        for url in urls:
            try: return await self._get(url,roll,cls,year,'Official BISE Gujranwala')
            except (AccessBlocked,CaptchaRequired,ResultNotAvailable,ProviderError) as e: last=e
        if self.fallback_url:
            try: return await self._get(self.fallback_url,roll,cls,year,'Configured fallback')
            except (AccessBlocked,CaptchaRequired,ResultNotAvailable,ProviderError): pass
        if isinstance(last,CaptchaRequired): raise last
        if isinstance(last,AccessBlocked): raise ProviderError('Official BISE source returned 403 Forbidden. Automated access is blocked; no bypass is attempted. Configure a lawful public fallback.')
        if isinstance(last,ProviderError): raise last
        raise ResultNotAvailable()

    async def _get(self,url,roll,cls,year,source):
        async with httpx.AsyncClient(follow_redirects=True,timeout=self.timeout,headers=self.headers) as c:
            try: r=await c.get(url)
            except httpx.HTTPError as e: raise ProviderError(f'HTTP request failed: {e}') from e
        if r.status_code==403: raise AccessBlocked()
        if r.status_code in (401,429): raise ProviderError(f'HTTP {r.status_code} from result provider.')
        if r.status_code>=500: raise ProviderError(f'Provider server error: HTTP {r.status_code}.')
        r.raise_for_status()
        soup=BeautifulSoup(r.text,'html.parser'); text=soup.get_text(' ',strip=True); low=text.lower()
        if any(x in low for x in ('captcha','recaptcha','verify you are human','security verification')): raise CaptchaRequired()
        result=self._parse(soup,roll,cls,year,source,url)
        if result is None: raise ResultNotAvailable()
        return result

    def _parse(self,soup,roll,cls,year,source,url):
        d={'roll_number':roll,'class_name':cls,'year':year,'name':None,'father_name':None,'status':'RESULT AVAILABLE','total_marks':None,'max_marks':None,'percentage':None,'grade':None,'subjects':{},'source':source,'source_url':url}
        for table in soup.find_all('table'):
            rows=[]
            for tr in table.find_all('tr'):
                cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])]
                if len(cells)>=2: rows.append(cells)
            for cells in rows:
                key=cells[0].lower(); val=' '.join(cells[1:]).strip()
                if 'roll' in key and re.search(r'\\d',val): d['roll_number']=re.search(r'\\d{3,10}',val).group()
                elif key in ('name','candidate name','student name'): d['name']=val
                elif 'father' in key: d['father_name']=val
                elif 'status' in key or key=='result': d['status']=val
                elif 'grade' in key: d['grade']=val
                elif 'percentage' in key or 'percent' in key: d['percentage']=self._num(val)
                elif 'total' in key and 'mark' in key: d['total_marks']=self._num(val)
                elif ('maximum' in key or 'max' in key) and 'mark' in key: d['max_marks']=self._num(val)
            if rows:
                h=[x.lower() for x in rows[0]]
                si=next((i for i,x in enumerate(h) if 'subject' in x),None); mi=next((i for i,x in enumerate(h) if 'mark' in x or 'obt' in x),None)
                if si is not None and mi is not None:
                    for row in rows[1:]:
                        if len(row)>max(si,mi):
                            n=self._num(row[mi]); s=row[si]
                            if n is not None and s and s.lower() not in ('total','grand total'): d['subjects'][s]=n
        if d['percentage'] is None and d['total_marks'] is not None and d['max_marks']: d['percentage']=round(d['total_marks']/d['max_marks']*100,2)
        evidence=roll in soup.get_text(' ',strip=True) or d['name'] or d['total_marks'] is not None or d['subjects']
        if not evidence: return None
        d['result_hash']=hashlib.sha256(repr(d).encode()).hexdigest(); return d

    @staticmethod
    def _num(v):
        m=re.search(r'\\d+(?:,\\d{3})*(?:\\.\\d+)?',str(v))
        return float(m.group().replace(',','')) if m else None
