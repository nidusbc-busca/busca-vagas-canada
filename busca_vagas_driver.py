import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Comunidades RCIP e Regiões de PNP Prioritárias
RCIP_COMMUNITIES = [
    "Thunder Bay", "Sudbury", "North Bay", "Sault Ste. Marie", "Timmins",
    "Brandon", "Alton/Rhineland", "Vernon", "West Kootenay", "Pictou County"
]

PNP_REGIONAL_CITIES = [
    "Prince Albert", "Moose Jaw", "Medicine Hat", "Grande Prairie",
    "Red Deer", "Lethbridge", "Moncton", "Saint John", "Fredericton"
]

TARGET_KEYWORDS = [
    "delivery driver", "courier", "driver", "chauffeur", 
    "passenger transportation", "shuttle driver", "service driver", 
    "route driver", "field service driver", "van driver"
]

SEARCH_TERMS = [
    "delivery driver",
    "courier driver",
    "shuttle driver",
    "class 4 driver"
]

def fetch_driver_jobs():
    base_url = "https://www.jobbank.gc.ca/jobsearch/jobsearch"
    jobs_found = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    seen_links = set()

    for term in SEARCH_TERMS:
        params = {"searchstring": term, "sort": "M"}
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                articles = soup.find_all("article")

                for article in articles[:10]:
                    link_elem = article.find("a", href=True)
                    if not link_elem:
                        continue
                    
                    link = "https://www.jobbank.gc.ca" + link_elem["href"]
                    if link in seen_links:
                        continue

                    title_elem = article.find("span", class_="noctitle")
                    location_elem = article.find("li", class_="location")
                    company_elem = article.find("li", class_="business")
                    salary_elem = article.find("li", class_="salary")

                    title = title_elem.get_text(strip=True) if title_elem else "N/A"
                    location = location_elem.get_text(strip=True) if location_elem else "N/A"
                    company = company_elem.get_text(strip=True) if company_elem else "N/A"
                    salary = salary_elem.get_text(strip=True) if salary_elem else "Não informado"

                    # Limpeza rápida da localização (remover texto extra do Job Bank)
                    location_clean = location.replace("Location", "").strip()

                    seen_links.add(link)
                    jobs_found.append({
                        "title": title,
                        "company": company,
                        "location": location_clean,
                        "salary": salary,
                        "link": link
                    })
        except Exception as e:
            print(f"Erro na busca pelo termo '{term}': {e}")

    return jobs_found

def analyze_job(job):
    title = job["title"].lower()
    location = job["location"]
    
    # 1. Dedução de NOC/TEER provável
    if any(k in title for k in ["courier", "delivery", "route"]):
        noc_teer = "NOC 73200 (TEER 3) - Delivery service drivers"
    elif any(k in title for k in ["shuttle", "chauffeur", "passenger"]):
        noc_teer = "NOC 73201 (TEER 3) - Taxi/Limousine/Shuttle drivers"
    elif "bus" in title:
        noc_teer = "NOC 73202 (TEER 3) - Bus drivers & transit operators"
    else:
        noc_teer = "NOC 74200 (TEER 4) - Other transport drivers"

    # 2. Requisito de Licença Estimado
    if "class 4" in title or "shuttle" in title or "passenger" in title:
        license_req = "Class 4 (Diretamente compatível com sua CNH BC Class 4 Restricted)"
    else:
        license_req = "Class 5 ou Class 4 Restricted (Totalmente compatível)"

    # 3. Potencial Migratório & Comunidade
    is_rcip = any(city.lower() in location.lower() for city in RCIP_COMMUNITIES)
    is_pnp_regional = any(city.lower() in location.lower() for city in PNP_REGIONAL_CITIES)
    is_vancouver = "vancouver" in location.lower() or "burnaby" in location.lower() or "richmond" in location.lower()

    if is_rcip:
        mig_potential = "🟢 ALTO — Comunidade participante do RCIP (Piloto Útil para Imigração Direta)"
        mig_program = "RCIP (Rural and Northern Immigration Pilot)"
    elif is_pnp_regional:
        mig_potential = "🟡 MÉDIO/ALTO — PNP Regional / Fora das grandes metrópoles"
        mig_program = "Provincial Nominee Program (PNP Regional)"
    elif is_vancouver:
        mig_potential = "🔴 BAIXO MIGRATÓRIO — Região Metropolitana de Vancouver (Alta competição / PNP restrito)"
        mig_program = "BC PNP General (Pontuação alta exigida)"
    else:
        mig_potential = "🟡 MÉDIO — Outras localidades canadenses"
        mig_program = "Express Entry / PNP Geral"

    # 4. Cálculo de Compatibilidade (Experiência + Licença + CLB 7)
    score = 70
    if any(kw in title for kw in TARGET_KEYWORDS):
        score += 15
    if "class 4" in title or "shuttle" in title or "courier" in title:
        score += 15

    score = min(score, 100)

    # 5. Classificação da vaga
    if score >= 85 and (is_rcip or is_pnp_regional):
        category = "🟢 APLICAR AGORA"
    elif score >= 75:
        category = "🟢 APLICAR"
    elif score >= 60:
        category = "🟡 INVESTIGAR"
    else:
        category = "🔴 NÃO PRIORITÁRIA"

    # Status de contratação estrangeira (Job Bank default)
    foreign_status = "Verificar no link oficial se a empresa aceita candidatos sem LMIA ou autorização vigente."

    return {
        "score": score,
        "noc_teer": noc_teer,
        "license_req": license_req,
        "mig_potential": mig_potential,
        "mig_program": mig_program,
        "category": category,
        "foreign_status": foreign_status
    }

def send_driver_report(jobs):
    if not EMAIL_USER or not EMAIL_PASS:
        print("ERRO: Credenciais de e-mail ausentes.")
        return

    analyzed_jobs = []
    for job in jobs:
        analysis = analyze_job(job)
        job_copy = job.copy()
        job_copy.update(analysis)
        analyzed_jobs.append(job_copy)

    # Ordenar por maior pontuação e melhor potencial migratório
    analyzed_jobs.sort(key=lambda x: x["score"], reverse=True)

    subject = "🚚 BUSCA DIÁRIA DE VAGAS — DRIVER (CLASS 4 & LOGÍSTICA CANADÁ)"

    body = "<h2>RELATÓRIO DIÁRIO DE OPORTUNIDADES PARA MOTORISTA</h2>"
    body += "<p><strong>Candidato:</strong> Class 4 Restricted (BC) | 3+ anos exp (Uber/Paceco/Quants + Brasil) | CLB 7 | Mobilidade total</p>"
    body += "<hr>"

    if not analyzed_jobs:
        body += "<p>Nenhuma oportunidade encontrada nos filtros de hoje.</p>"
    else:
        # Renderização por Categorias
        for cat in ["🟢 APLICAR AGORA", "🟢 APLICAR", "🟡 INVESTIGAR", "🔴 NÃO PRIORITÁRIA"]:
            category_jobs = [j for j in analyzed_jobs if j["category"] == cat]
            if category_jobs:
                body += f"<h3>{cat}</h3>"
                for j in category_jobs:
                    body += f"<div style='margin-bottom: 15px; padding: 10px; border-left: 4px solid #007bff; background-color: #f9f9f9;'>"
                    body += f"<h4>{j['company'].upper()} — {j['title']}</h4>"
                    body += f"<p>📍 <strong>Cidade/Província:</strong> {j['location']}<br>"
                    body += f"💰 <strong>Salário:</strong> {j['salary']}<br>"
                    body += f"🪪 <strong>Requisito de Licença:</strong> {j['license_req']}<br>"
                    body += f"📌 <strong>NOC / TEER Provável:</strong> {j['noc_teer']}<br>"
                    body += f"📊 <strong>Compatibilidade com Perfil:</strong> {j['score']}%<br>"
                    body += f"🍁 <strong>Potencial Migratório:</strong> {j['mig_potential']}<br>"
                    body += f"🏛️ <strong>Programa/Comunidade:</strong> {j['mig_program']}<br>"
                    body += f"🌐 <strong>Contratação Estrangeira:</strong> {j['foreign_status']}<br>"
                    body += f"🔗 <a href='{j['link']}'>Ver vaga e candidatar-se no Job Bank</a></p>"
                    body += f"</div>"

        # TOP 5 Oportunidades do Dia
        top_5 = analyzed_jobs[:5]
        body += "<hr><h2>⭐ TOP 5 OPORTUNIDADES DO DIA</h2><ol>"
        for item in top_5:
            body += f"<li><strong>{item['title']}</strong> - {item['company']} ({item['location']}) — <em>Score: {item['score']}%</em></li>"
        body += "</ol>"

        # Recomendação Estratégica
        body += "<hr><h2>🎯 RECOMENDAÇÃO ESTRATÉGICA</h2>"
        body += "<p>Priorize candidaturas localizadas em comunidades <strong>RCIP (ex: Thunder Bay, Sudbury, Vernon)</strong> e regiões fora do Lower Mainland (Vancouver). "
        body += "Embora as vagas de motorista em Vancouver ofereçam contratação rápida para renda imediata, o potencial migratório por PNP em Vancouver é significativamente mais baixo do que em regiões menores ou províncias do interior.</p>"

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
        print(">>> E-MAIL DE VAGAS DE DRIVER ENVIADO COM SUCESSO! <<<")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

if __name__ == "__main__":
    vagas = fetch_driver_jobs()
    send_driver_report(vagas)
