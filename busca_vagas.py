import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

PRIORITY_CITIES = {
    "P1": ["Thunder Bay", "Sudbury", "North Bay", "Sault Ste. Marie", "Timmins"],
    "P2": [
        "Brandon",
        "Prince Albert",
        "Moose Jaw",
        "Medicine Hat",
        "Grande Prairie",
    ],
}

TARGET_KEYWORDS = [
    "network technician",
    "telecommunications technician",
    "data centre technician",
    "data center technician",
    "infrastructure technician",
    "telecom supervisor",
    "field service technician",
    "network administrator",
]

TARGET_COMPANIES = [
    "tbaytel",
    "vianet",
    "eastlink",
    "xplore",
    "ledcor",
    "bell",
    "rogers",
    "afl",
    "estruxture",
]


def fetch_job_bank_jobs():
    base_url = "https://www.jobbank.gc.ca/jobsearch/jobsearch"
    jobs_found = []
    params = {"searchstring": "network technician", "sort": "M"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(base_url, params=params, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.find_all("article")

            for article in articles[:10]:
                title_elem = article.find("span", class_="noctitle")
                location_elem = article.find("li", class_="location")
                company_elem = article.find("li", class_="business")
                link_elem = article.find("a", href=True)

                if title_elem and location_elem and link_elem:
                    title = title_elem.get_text(strip=True)
                    location = location_elem.get_text(strip=True)
                    company = (
                        company_elem.get_text(strip=True)
                        if company_elem
                        else "N/A"
                    )
                    link = "https://www.jobbank.gc.ca" + link_elem["href"]

                    jobs_found.append(
                        {
                            "title": title,
                            "company": company,
                            "location": location,
                            "link": link,
                        }
                    )
    except Exception as e:
        print(f"Erro na busca: {e}")

    return jobs_found


def calculate_scores(job):
    title = job["title"].lower()
    location = job["location"]
    company = job["company"].lower()

    prof_score = 65
    if any(kw in title for kw in TARGET_KEYWORDS):
        prof_score += 20
    if any(c in company for c in TARGET_COMPANIES):
        prof_score += 15

    prof_score = min(prof_score, 100)

    mig_potential = "🔴 BAIXA"
    if any(city.lower() in location.lower() for city in PRIORITY_CITIES["P1"]):
        mig_potential = "🟢 ALTA (RCIP / ON PNP)"
    elif any(city.lower() in location.lower() for city in PRIORITY_CITIES["P2"]):
        mig_potential = "🟡 MÉDIA (PNP Regional)"

    if prof_score >= 85 and "ALTA" in mig_potential:
        recommendation = "🟢 APLICAR AGORA"
    elif prof_score >= 75:
        recommendation = "🟢 APLICAR"
    elif prof_score >= 60:
        recommendation = "🟡 INVESTIGAR"
    else:
        recommendation = "🔴 NÃO PRIORITÁRIA"

    return prof_score, mig_potential, recommendation


def send_email_report(jobs):
    if not EMAIL_USER or not EMAIL_PASS:
        print("ERRO: Credenciais de e-mail não encontradas nos Secrets.")
        return

    subject = "🤖 BUSCA DIÁRIA — NOC 22220 / TELECOM / DATA CENTER"

    body = "<h2>BUSCA DIÁRIA — NOC 22220 / TELECOM / DATA CENTER</h2>"
    body += "<p><strong>Localização Atual:</strong> Vancouver, BC (Aberto à mudança)</p><hr>"

    if not jobs:
        body += "<p>Nenhuma vaga nova encontrada no filtro de hoje.</p>"
    else:
        for idx, job in enumerate(jobs, 1):
            prof_score, mig_potential, recommendation = calculate_scores(job)

            body += (
                f"<h3>{idx}. {job['company'].upper()} — {job['title']}</h3>"
            )
            body += f"<p>📍 <strong>Cidade:</strong> {job['location']}<br>"
            body += f"📊 <strong>Compatibilidade Profissional:</strong> {prof_score}%<br>"
            body += f"🍁 <strong>Potencial Migratório:</strong> {mig_potential}<br>"
            body += f"🎯 <strong>Recomendação:</strong> {recommendation}<br>"
            body += f"⚠️ <strong>Work Permit:</strong> Necessário verificar autorização antes.<br>"
            body += f"🔗 <a href='{job['link']}'>Ver Vaga no Job Bank</a></p><hr>"

        body += "<h4>🎯 ESTRATÉGIA DO DIA:</h4>"
        body += "<p>Priorize candidaturas em cidades P1 (RCIP) e verifique autorização de alteração de empregador.</p>"

    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        try:
            server.quit()
        except Exception:
            pass
        print(">>> E-MAIL ENVIADO COM SUCESSO! <<<")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")


if __name__ == "__main__":
    vagas = fetch_job_bank_jobs()
