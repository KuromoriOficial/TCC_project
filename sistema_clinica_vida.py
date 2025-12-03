#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clínica Vida+ — Versão atualizada
Alterações aplicadas:
- Seleção de médico por número (como faturamento) na criação/edição de agendamentos
- Padronização de '0' como opção Sair/Voltar em menus
- Nome do menu do médico alterado para "Agendamentos de Serviços"
Arquivos em dados/: users.json, pacientes.json, appointments.json, invoices.json, notifications.json, actions.log, pacientes.csv, relatorio_estatisticas.txt
"""

import os, json, csv, re, difflib
from datetime import datetime
from collections import deque

# ------------------------
# CONFIG / ARQUIVOS
# ------------------------
DATA_DIR = "dados"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
PATIENTS_FILE = os.path.join(DATA_DIR, "pacientes.json")
APPTS_FILE = os.path.join(DATA_DIR, "appointments.json")
INVOICES_FILE = os.path.join(DATA_DIR, "invoices.json")
NOTIFS_FILE = os.path.join(DATA_DIR, "notifications.json")
LOG_FILE = os.path.join(DATA_DIR, "actions.log")
CSV_FILE = os.path.join(DATA_DIR, "pacientes.csv")
REPORT_FILE = os.path.join(DATA_DIR, "relatorio_estatisticas.txt")

AUTH_CODE = "GESTAO-2025-CODE"

def ensure(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)

ensure(USERS_FILE, [])
ensure(PATIENTS_FILE, [])
ensure(APPTS_FILE, [])
ensure(INVOICES_FILE, [])
ensure(NOTIFS_FILE, [])
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("Log Clínica Vida+\n")

# ------------------------
# UTILITÁRIOS
# ------------------------
def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_action(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now_ts()}] {msg}\n")

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def reload_all():
    global users, patients, appointments, invoices, notifications
    users = load_json(USERS_FILE)
    patients = load_json(PATIENTS_FILE)
    appointments = load_json(APPTS_FILE)
    invoices = load_json(INVOICES_FILE)
    notifications = load_json(NOTIFS_FILE)

reload_all()

# ------------------------
# VALIDAÇÕES E FORMATAÇÃO
# ------------------------
def only_digits(s): return re.sub(r"\D", "", s or "")

def validar_idade(v):
    try:
        i = int(v); return i if i >= 0 else None
    except:
        return None

def validar_telefone_raw(tel):
    d = only_digits(tel)
    return len(d) in (10, 11)

def format_telefone(tel):
    d = only_digits(tel)
    if len(d) < 10:
        return tel.strip()
    ddd = d[:2]; rest = d[2:]
    if len(rest) == 8:
        return f"({ddd}) {rest[:4]}-{rest[4:]}"
    if len(rest) == 9:
        return f"({ddd}) {rest[:5]}-{rest[5:]}"
    last9 = rest[-9:]; return f"({ddd}) {last9[:5]}-{last9[5:]}"

# ------------------------
# USUÁRIOS / AUTENTICAÇÃO
# ------------------------
def find_user(username):
    reload_all()
    return next((u for u in users if u['username'] == username), None)

def criar_usuario(role, username=None, password=None, name=None, skip_auth=False):
    reload_all()
    if username is None:
        username = input("Username: ").strip()
    if find_user(username):
        print("Usuário já existe.")
        return None
    if role == "medico" and not skip_auth:
        code = input("Insira o código de autorização (peça à Gestão) ou '0' para voltar: ").strip()
        if code == "0":
            return None
        if code != AUTH_CODE:
            print("Código inválido. Você pode Notificar a Gestão em vez disso.")
            return None
    if password is None:
        password = input("Senha: ").strip()
    if name is None:
        name = input("Nome completo: ").strip()
    user = {"username": username, "password": password, "role": role, "name": name}
    users.append(user)
    save_json(USERS_FILE, users)
    log_action(f"Usuário criado: {username} ({role})")
    if role == "paciente":
        if not next((p for p in patients if p.get("user") == username), None):
            p = {"nome": name, "idade": 0, "telefone": "Não informado", "user": username}
            patients.append(p)
            save_json(PATIENTS_FILE, patients)
            log_action(f"Paciente criado e vinculado ao user {username}")
    return user

def autenticar(role_expected):
    reload_all()
    print(f"\n-- Login ({role_expected}) --")
    username = input("Username: ").strip()
    password = input("Senha: ").strip()
    user = find_user(username)
    if not user or user.get("password") != password:
        print("Usuário ou senha inválidos.")
        return None
    if user.get("role") != role_expected:
        print(f"Permissão incorreta. Você é '{user.get('role')}', não '{role_expected}'.")
        return None
    log_action(f"Login: {username} role={role_expected}")
    return user

# ------------------------
# PACIENTES
# ------------------------
def find_patient_by_user(username):
    reload_all()
    return next((p for p in patients if p.get("user") == username), None)

def patient_view_own(user):
    p = find_patient_by_user(user['username'])
    if not p:
        print("Nenhum cadastro vinculado ao seu usuário. Peça à gestão para vincular.")
        return
    print("\n--- Meu cadastro ---")
    print(f"Nome: {p.get('nome')}")
    print(f"Idade: {p.get('idade')}")
    print(f"Telefone: {p.get('telefone')}")
    print(f"Username vinculado: {p.get('user')}")

def listar_todos_pacientes_compacto():
    reload_all()
    if not patients:
        print("Nenhum paciente cadastrado.")
        return
    for i, p in enumerate(patients, start=1):
        print(f"{i}. {p.get('nome')} | {p.get('idade')} | {p.get('telefone')} | user: {p.get('user','-')}")

# ------------------------
# MÉDICOS — listagem para seleção numérica
# ------------------------
def listar_medicos_compacto():
    reload_all()
    medicos = [u for u in users if u.get("role") == "medico"]
    if not medicos:
        print("Nenhum médico cadastrado.")
        return []
    for i, m in enumerate(medicos, start=1):
        print(f"{i}. {m.get('name')} (username: {m.get('username')})")
    return medicos

def escolher_medico_por_numero(prompt="Escolha o médico pelo número (ou 0 para não atribuir): "):
    medicos = [u for u in users if u.get("role") == "medico"]
    if not medicos:
        print("Nenhum médico cadastrado; continuará sem médico atribuído.")
        return None
    for i, m in enumerate(medicos, start=1):
        print(f"{i}. {m.get('name')} (username: {m.get('username')})")
    sel = input(prompt).strip()
    if sel == "0" or sel == "":
        return None
    try:
        n = int(sel)
        if 1 <= n <= len(medicos):
            return medicos[n-1]['username']
    except:
        pass
    print("Seleção inválida. Nenhum médico atribuído.")
    return None

# ------------------------
# AGENDAMENTOS (criar/listar/editar/cancelar/remover)
# ------------------------
def new_appt_id():
    reload_all()
    if not appointments: return 1
    return max(a.get("id",0) for a in appointments) + 1

def cadastrar_agendamento(patient_user, patient_name):
    reload_all()
    print("\n--- Criar Agendamento ---")
    doc_user = escolher_medico_por_numero("Digite o número do médico (ou 0 para não atribuir): ")
    dt = input("Data/Horário (ex: 2025-08-10 14:30): ").strip()
    notes = input("Observações (opcional): ").strip()
    appt = {"id": new_appt_id(), "patient_user": patient_user, "patient_name": patient_name,
            "doctor_user": doc_user, "datetime": dt, "status": "agendado", "notes": notes}
    appointments.append(appt)
    save_json(APPTS_FILE, appointments)
    log_action(f"Agendamento criado ID {appt['id']} paciente {patient_user} médico {doc_user}")
    print(f"Agendamento criado: ID {appt['id']}")

def listar_todos_agendamentos():
    reload_all()
    if not appointments:
        print("Nenhum agendamento.")
        return
    for a in appointments:
        print(f"ID {a['id']} - Paciente: {a['patient_name']} (user:{a.get('patient_user')}) - Médico:{a.get('doctor_user') or 'Não atribuído'} - {a['datetime']} - {a['status']}")

def listar_meus_agendamentos(patient_user):
    reload_all()
    return [a for a in appointments if a.get("patient_user") == patient_user]

def paciente_agendamentos_menu(user):
    while True:
        print("\n--- Meus Agendamentos ---")
        print("1. Listar")
        print("2. Editar")
        print("3. Cancelar (marca)")
        print("4. Remover (apagar)")
        print("0. Voltar")
        op = input("Escolha: ").strip()
        if op == "1":
            meus = listar_meus_agendamentos(user['username'])
            if not meus:
                print("Nenhum agendamento.")
            else:
                for a in meus:
                    print(f"ID {a['id']} - {a['datetime']} - Médico: {a.get('doctor_user') or 'Não atribuído'} - Status: {a['status']}")
        elif op == "2":
            meus = listar_meus_agendamentos(user['username'])
            if not meus: print("Nenhum agendamento para editar."); continue
            for a in meus: print(f"ID {a['id']} - {a['datetime']} - Status: {a['status']} - Médico: {a.get('doctor_user') or '—'}")
            id_txt = input("ID para editar (ou 0 para voltar): ").strip()
            if id_txt == "0":
                continue
            try:
                id_int = int(id_txt)
                ap = next(a for a in appointments if a['id']==id_int and a['patient_user']==user['username'])
            except:
                print("ID inválido."); continue
            print("Selecione o novo médico (ou 0 para manter/nenhum):")
            novo_doc = escolher_medico_por_numero("Número do médico (ou 0): ")
            novo_dt = input(f"Novo Data/Horário [{ap['datetime']}] (ENTER = manter): ").strip() or ap['datetime']
            if novo_doc is None:
                novo_doc = ap.get('doctor_user')
            ap['datetime'] = novo_dt; ap['doctor_user'] = novo_doc
            save_json(APPTS_FILE, appointments)
            log_action(f"Paciente {user['username']} editou agendamento {id_int}")
            print("Agendamento atualizado.")
        elif op == "3":
            meus = listar_meus_agendamentos(user['username'])
            if not meus: print("Nenhum agendamento para cancelar."); continue
            for a in meus: print(f"ID {a['id']} - {a['datetime']} - Status: {a['status']}")
            id_txt = input("ID para cancelar (ou 0 voltar): ").strip()
            if id_txt == "0": continue
            try:
                id_int = int(id_txt)
                ap = next(a for a in appointments if a['id']==id_int and a['patient_user']==user['username'])
            except:
                print("ID inválido."); continue
            ap['status'] = "cancelado"; save_json(APPTS_FILE, appointments)
            log_action(f"Paciente {user['username']} cancelou agendamento {id_int}")
            print("Agendamento marcado como CANCELADO.")
        elif op == "4":
            meus = listar_meus_agendamentos(user['username'])
            if not meus: print("Nenhum agendamento para remover."); continue
            for a in meus: print(f"ID {a['id']} - {a['datetime']} - Status: {a['status']}")
            id_txt = input("ID para remover definitivamente (ou 0 voltar): ").strip()
            if id_txt == "0": continue
            try:
                id_int = int(id_txt)
                ap = next(a for a in appointments if a['id']==id_int and a['patient_user']==user['username'])
            except:
                print("ID inválido."); continue
            confirm = input("Tem certeza que deseja REMOVER este agendamento? (S/N): ").strip().lower()
            if confirm == "s":
                appointments.remove(ap); save_json(APPTS_FILE, appointments)
                log_action(f"Paciente {user['username']} removeu agendamento {id_int}")
                print("Agendamento REMOVIDO.")
            else:
                print("Operação cancelada.")
        elif op == "0":
            break
        else:
            print("Inválido.")

def ver_agendamentos_medico(doctor_user):
    reload_all()
    meus = [a for a in appointments if a.get("doctor_user") == doctor_user]
    if not meus:
        print("Nenhum agendamento atribuído a você.")
        return
    for a in meus:
        print(f"ID {a['id']} - Paciente: {a['patient_name']} - {a['datetime']} - Status: {a['status']} - Obs: {a.get('notes','')}")

def editar_status_agendamento_medico(doctor_user):
    ver_agendamentos_medico(doctor_user)
    id_txt = input("ID do agendamento para alterar status (ou 0 voltar): ").strip()
    if id_txt == "0":
        return
    try:
        id_int = int(id_txt)
        ap = next(a for a in appointments if a['id']==id_int and a.get('doctor_user')==doctor_user)
    except:
        print("ID inválido ou não é seu agendamento."); return
    novo = input("Novo status (agendado/confirmado/concluido/cancelado): ").strip().lower()
    if novo not in ("agendado","confirmado","concluido","cancelado"):
        print("Status inválido."); return
    ap['status'] = novo; save_json(APPTS_FILE, appointments)
    log_action(f"Dr {doctor_user} atualizou status agendamento {id_int} -> {novo}")
    print("Status atualizado.")

# ------------------------
# NOTIFICAÇÕES (gestão)
# ------------------------
def notify_management(attempt_username, attempt_name, message):
    reload_all()
    notif = {"timestamp": now_ts(), "attempt_username": attempt_username, "attempt_name": attempt_name, "message": message}
    notifications.append(notif); save_json(NOTIFS_FILE, notifications)
    log_action(f"Notificação criada: {attempt_username} / {attempt_name} -> {message}")

def admin_show_notifications():
    reload_all()
    if not notifications:
        print("Sem notificações.")
        return
    for n in notifications:
        print(f"[{n['timestamp']}] Usuário: {n['attempt_username']} / Nome: {n['attempt_name']} -> {n['message']}")

# ------------------------
# FATURAS (gestão por número)
# ------------------------
def new_invoice_id():
    reload_all()
    if not invoices: return 1
    return max(i.get("id",0) for i in invoices) + 1

def choose_patient_by_number():
    reload_all()
    if not patients:
        print("Nenhum paciente cadastrado."); return None
    print("\nEscolha o paciente (número):")
    for idx, p in enumerate(patients, start=1):
        print(f"{idx}. {p.get('nome')} (user: {p.get('user','')})")
    sel = input("Número do paciente (ou 0 para cancelar): ").strip()
    if sel == "0" or sel == "":
        return None
    try:
        n = int(sel)
        if 1 <= n <= len(patients):
            return patients[n-1]
    except:
        pass
    print("Seleção inválida."); return None

def admin_create_invoice_for_patient():
    p = choose_patient_by_number()
    if not p: return
    patient_user = p.get('user') or input("Este paciente não tem username vinculado. Digite username (ou 0 cancelar): ").strip()
    if not patient_user or patient_user == "0":
        print("Operação cancelada."); return
    total_txt = input("Valor total: ").strip()
    try:
        total = float(total_txt.replace(",","." ))
    except:
        print("Valor inválido."); return
    n_txt = input("Número de parcelas: ").strip()
    try:
        n = int(n_txt); assert n > 0
    except:
        print("Parcelas inválidas."); return
    base = round(total / n, 2); remaining = total
    parcels = []
    for i in range(1, n+1):
        if i < n: amt = base
        else: amt = round(remaining, 2)
        parcels.append({"number": i, "amount": amt, "paid": False})
        remaining -= amt
    inv = {"id": new_invoice_id(), "patient_user": patient_user, "total": total, "parcels": parcels, "created_at": now_ts()}
    invoices.append(inv); save_json(INVOICES_FILE, invoices)
    log_action(f"Gestão criou fatura {inv['id']} para {patient_user}")
    print(f"Fatura criada ID {inv['id']}")

def admin_list_invoices():
    reload_all()
    if not invoices:
        print("Nenhuma fatura.")
        return
    for inv in invoices:
        print(f"ID {inv['id']} - paciente_user {inv['patient_user']} - total {inv['total']} - criada {inv['created_at']}")
        for p in inv['parcels']:
            print(f"   Parcela {p['number']}: {p['amount']} - {'PAGA' if p['paid'] else 'PENDENTE'}")

def admin_edit_invoice_parcel():
    admin_list_invoices()
    id_txt = input("ID da fatura (ou 0 para voltar): ").strip()
    if id_txt == "0": return
    try:
        id_int = int(id_txt); inv = next(i for i in invoices if i['id']==id_int)
    except:
        print("ID inválido."); return
    for p in inv['parcels']:
        print(f"Parcela {p['number']}: {p['amount']} - {'PAGA' if p['paid'] else 'PENDENTE'}")
    num_txt = input("Nº da parcela para alternar paga/não paga (ou 0 voltar): ").strip()
    if num_txt == "0": return
    try:
        num = int(num_txt); parc = next(p for p in inv['parcels'] if p['number']==num)
    except:
        print("Parcela inválida."); return
    parc['paid'] = not parc['paid']; save_json(INVOICES_FILE, invoices)
    log_action(f"Gestão alternou parcela {num} da fatura {id_int} -> {'PAGA' if parc['paid'] else 'PENDENTE'}")
    print("Alteração salva.")

def admin_remove_invoice():
    admin_list_invoices()
    id_txt = input("ID para remover (ou 0 voltar): ").strip()
    if id_txt == "0": return
    try:
        id_int = int(id_txt); inv = next(i for i in invoices if i['id']==id_int)
        invoices.remove(inv); save_json(INVOICES_FILE, invoices); log_action(f"Gestão removeu fatura {id_int}"); print("Removido.")
    except:
        print("Inválido.")

def patient_view_my_invoices_menu(user):
    while True:
        print("\n--- Minhas Faturas ---")
        print("1. Ver minhas faturas")
        print("0. Voltar")
        op = input("Escolha: ").strip()
        if op == "1":
            reload_all()
            my = [inv for inv in invoices if inv.get("patient_user") == user['username']]
            if not my:
                print("Nenhuma fatura encontrada.")
            else:
                for inv in my:
                    print(f"ID {inv['id']} - Total {inv['total']} - Criada {inv['created_at']}")
                    for p in inv['parcels']:
                        print(f"   Parcela {p['number']}: {p['amount']} - {'PAGA' if p['paid'] else 'PENDENTE'}")
                    pend = sum(1 for p in inv['parcels'] if not p['paid'])
                    print(f"   Parcelas pendentes: {pend}\n")
        elif op == "0":
            break
        else:
            print("Inválido.")

def medico_consultar_faturas():
    reload_all()
    uname = input("Username do paciente (ou 0 voltar): ").strip()
    if uname == "0" or uname == "":
        return
    my = [inv for inv in invoices if inv.get("patient_user") == uname]
    if not my:
        print("Nenhuma fatura para esse paciente.")
    else:
        for inv in my:
            print(f"ID {inv['id']} - Total {inv['total']} - Criada {inv['created_at']}")
            for p in inv['parcels']:
                print(f"   Parcela {p['number']}: {p['amount']} - {'PAGA' if p['paid'] else 'PENDENTE'}")

# ------------------------
# LÓGICA BOOLEANA (Passo 3)
# ------------------------
def avaliar_regras(A: bool, B: bool, C: bool, D: bool):
    consulta_normal = (A and B and C) or (B and C and D)
    emergencia = C and (B or D)
    return consulta_normal, emergencia

def bool_to_vf(b): return "V" if b else "F"

def tabela_verdade_consulta():
    print("\nTabela Verdade — CONSULTA NORMAL (A B C D | Res)")
    for n in range(16):
        A = bool(n & 8); B = bool(n & 4); C = bool(n & 2); D = bool(n & 1)
        res, _ = avaliar_regras(A,B,C,D)
        print(f"{bool_to_vf(A)} {bool_to_vf(B)} {bool_to_vf(C)} {bool_to_vf(D)} | {bool_to_vf(res)}")

def tabela_verdade_emergencia():
    print("\nTabela Verdade — EMERGÊNCIA (A B C D | Res)")
    for n in range(16):
        A = bool(n & 8); B = bool(n & 4); C = bool(n & 2); D = bool(n & 1)
        _, res = avaliar_regras(A,B,C,D)
        print(f"{bool_to_vf(A)} {bool_to_vf(B)} {bool_to_vf(C)} {bool_to_vf(D)} | {bool_to_vf(res)}")

def contar_situacoes_regra():
    total_cons = sum(1 for n in range(16) if avaliar_regras(bool(n&8), bool(n&4), bool(n&2), bool(n&1))[0])
    total_emerg = sum(1 for n in range(16) if avaliar_regras(bool(n&8), bool(n&4), bool(n&2), bool(n&1))[1])
    print(f"Consulta Normal atende em {total_cons} de 16 situações.")
    print(f"Emergência atende em {total_emerg} de 16 situações.")

def testar_caso_pratico():
    A=False; B=True; C=True; D=False
    cons, emerg = avaliar_regras(A,B,C,D)
    print("\nCaso prático: A=F B=V C=V D=F")
    print(f"Consulta Normal: {bool_to_vf(cons)} -> {'ATENDE' if cons else 'NÃO ATENDE'}")
    print(f"Emergência: {bool_to_vf(emerg)} -> {'ATENDE' if emerg else 'NÃO ATENDE'}")

# ------------------------
# EXPORT / RELATÓRIO / FILA
# ------------------------
def exportar_csv(filename=CSV_FILE):
    reload_all()
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["nome","idade","telefone","user"], delimiter=';')
        writer.writeheader()
        for p in patients:
            writer.writerow({"nome": p.get("nome"), "idade": p.get("idade"), "telefone": p.get("telefone"), "user": p.get("user","")})
    log_action("CSV exportado")
    print("CSV exportado:", filename)

def gerar_relatorio_txt(path=REPORT_FILE):
    reload_all()
    if not patients:
        print("Sem pacientes.")
        return
    total = len(patients); media = sum(p['idade'] for p in patients)/total if total else 0
    with open(path, "w", encoding="utf-8") as f:
        f.write("Relatório Clínica Vida+\n")
        f.write("="*40 + "\n")
        f.write(f"Total pacientes: {total}\nIdade média: {media:.2f}\n\n")
        f.write("Pacientes:\n")
        for p in patients:
            f.write(f"- {p.get('nome')} | {p.get('idade')} | {p.get('telefone')} | user: {p.get('user','')}\n")
    log_action("Relatório gerado")
    print("Relatório gerado:", path)

def simular_fila():
    fila = deque()
    for i in range(1,4):
        nome = input(f"Nome paciente {i}: ").strip(); cpf = input(f"CPF paciente {i}: ").strip()
        fila.append({"nome": nome, "cpf": cpf})
    print("\nFila atual:")
    for idx,p in enumerate(fila, start=1):
        print(f"{idx}. {p['nome']} | {p['cpf']}")
    atendido = fila.popleft()
    print(f"\nAtendido: {atendido['nome']} | {atendido['cpf']}")
    if fila:
        print("\nRestantes:")
        for idx,p in enumerate(fila, start=1):
            print(f"{idx}. {p['nome']} | {p['cpf']}")
    else:
        print("Fila vazia.")

# ------------------------
# HUBs (menus) — padronizando 0 como voltar/sair
# ------------------------
def medico_create_hub():
    while True:
        print("\n--- Criação de conta (Médico) ---")
        print("1. Inserir código de autorização")
        print("2. Notificar a gestão (envia aviso, não cria o usuário automaticamente)")
        print("0. Voltar")
        opt = input("Escolha: ").strip()
        if opt == "1":
            code = input("Código (ou 0 voltar): ").strip()
            if code == "0":
                continue
            if code != AUTH_CODE:
                print("Código inválido."); continue
            username = input("Username desejado: ").strip()
            if find_user(username):
                print("Username já existe."); continue
            password = input("Senha: ").strip(); name = input("Nome completo: ").strip()
            criar_usuario("medico", username=username, password=password, name=name, skip_auth=True)
            print("Conta médica criada.")
        elif opt == "2":
            attempted_username = input("Username desejado: ").strip()
            attempted_name = input("Nome completo: ").strip()
            message = input("Mensagem para a gestão: ").strip()
            notify_management(attempted_username, attempted_name, message)
            print("Notificação enviada para a gestão.")
        elif opt == "0":
            break
        else:
            print("Inválido.")

def hub_paciente(user):
    while True:
        print(f"\n--- HUB Paciente ({user['name']}) ---")
        print("1. Ver meu cadastro")
        print("2. Editar meu cadastro")
        print("3. Agendar consulta")
        print("4. Meus agendamentos (listar/editar/cancelar/remover)")
        print("5. Minhas faturas")
        print("0. Sair")
        op = input("Escolha: ").strip()
        if op == "1":
            patient_view_own(user)
        elif op == "2":
            p = find_patient_by_user(user['username'])
            if not p:
                print("Nenhum cadastro vinculado. Peça à gestão.")
                continue
            novo = input(f"Novo nome [{p['nome']}]: ").strip() or p['nome']
            idade_txt = input(f"Nova idade [{p['idade']}]: ").strip()
            idade = validar_idade(idade_txt) if idade_txt else p['idade']
            tel_in = input(f"Novo telefone [{p['telefone']}]: ").strip() or p['telefone']
            if tel_in and validar_telefone_raw(tel_in):
                tel = format_telefone(tel_in)
            else:
                tel = tel_in
            p['nome'] = novo; p['idade'] = idade; p['telefone'] = tel
            save_json(PATIENTS_FILE, patients)
            log_action(f"Paciente {user['username']} atualizou seu cadastro")
            print("Cadastro atualizado.")
        elif op == "3":
            if not find_patient_by_user(user['username']):
                patients.append({"nome": user['name'], "idade": 0, "telefone": "Não informado", "user": user['username']})
                save_json(PATIENTS_FILE, patients)
            cadastrar_agendamento(user['username'], user['name'])
        elif op == "4":
            paciente_agendamentos_menu(user)
        elif op == "5":
            patient_view_my_invoices_menu(user)
        elif op == "0":
            break
        else:
            print("Inválido.")

def hub_medico(user):
    while True:
        print(f"\n--- Agendamentos de Serviços ({user['name']}) ---")
        print("1. Ver meus agendamentos")
        print("2. Editar status de agendamento")
        print("3. Consultar faturas de paciente")
        print("4. Ver todos pacientes")
        print("0. Sair")
        op = input("Escolha: ").strip()
        if op == "1":
            ver_agendamentos_medico(user['username'])
        elif op == "2":
            editar_status_agendamento_medico(user['username'])
        elif op == "3":
            medico_consultar_faturas()
        elif op == "4":
            listar_todos_pacientes_compacto()
        elif op == "0":
            break
        else:
            print("Inválido.")

def admin_create_user():
    role = input("Role (paciente/medico/gestao) ou 0 para voltar: ").strip().lower()
    if role == "0": return
    if role not in ("paciente","medico","gestao"):
        print("Role inválida."); return
    if role == "medico":
        criar_usuario("medico", skip_auth=True)
    else:
        criar_usuario(role)

def admin_remove_user():
    reload_all()
    for i,u in enumerate(users, start=1):
        print(f"{i}. {u['username']} | {u['name']} | {u['role']}")
    idx = input("Número do usuário a remover (ou 0 voltar): ").strip()
    if idx == "0": return
    try:
        i = int(idx)-1; u = users.pop(i); save_json(USERS_FILE, users); log_action(f"Gestão removeu usuário {u['username']}"); print("Removido.")
    except:
        print("Inválido.")

def admin_crud_patients():
    while True:
        print("\n-- CRUD Pacientes --")
        print("1. Listar 2. Criar 3. Editar 4. Remover 0. Voltar")
        op = input("Escolha: ").strip()
        if op == "1":
            listar_todos_pacientes_compacto()
        elif op == "2":
            nome = input("Nome: ").strip(); idade = validar_idade(input("Idade: ").strip()) or 0
            tel = input("Telefone: ").strip() or "Não informado"; userlink = input("Username vinculado (opcional, 0 p/nenhum): ").strip() or None
            if userlink == "0": userlink = None
            p = {"nome": nome, "idade": idade, "telefone": tel}
            if userlink: p["user"] = userlink
            patients.append(p); save_json(PATIENTS_FILE, patients); log_action(f"Gestão criou paciente {nome}")
        elif op == "3":
            listar_todos_pacientes_compacto(); idx = input("Número do paciente editar (ou 0 voltar): ").strip()
            if idx == "0": continue
            try:
                i = int(idx)-1; p = patients[i]
            except: print("Inválido"); continue
            p['nome'] = input(f"Nome [{p['nome']}]: ").strip() or p['nome']
            idade_txt = input(f"Idade [{p['idade']}]: ").strip(); p['idade'] = validar_idade(idade_txt) if idade_txt else p['idade']
            p['telefone'] = input(f"Telefone [{p['telefone']}]: ").strip() or p['telefone']
            p['user'] = input(f"Username vinculado [{p.get('user','')}]: ").strip() or p.get('user')
            save_json(PATIENTS_FILE, patients); log_action(f"Gestão editou paciente {p['nome']}")
        elif op == "4":
            listar_todos_pacientes_compacto(); idx = input("Número do paciente remover (ou 0 voltar): ").strip()
            if idx == "0": continue
            try:
                i = int(idx)-1; p = patients.pop(i); save_json(PATIENTS_FILE, patients); log_action(f"Gestão removeu paciente {p['nome']}"); print("Removido.")
            except: print("Inválido.")
        elif op == "0":
            break
        else:
            print("Inválido.")

def admin_manage_invoices_menu():
    while True:
        print("\n-- Gestão Faturas --")
        print("1. Listar 2. Criar 3. Editar parcela 4. Remover 0. Voltar")
        op = input("Escolha: ").strip()
        if op == "1": admin_list_invoices()
        elif op == "2": admin_create_invoice_for_patient()
        elif op == "3": admin_edit_invoice_parcel()
        elif op == "4": admin_remove_invoice()
        elif op == "0": break
        else: print("Inválido.")

def admin_manage_appointments():
    reload_all()
    if not appointments:
        print("Nenhum agendamento.")
        return
    for a in appointments:
        print(f"ID {a['id']} - Paciente: {a['patient_name']} user:{a.get('patient_user')} - Médico:{a.get('doctor_user') or 'Não atribuído'} - {a['datetime']} - {a['status']}")

def admin_show_notifications():
    admin_show_notifications = globals().get('admin_show_notifications')  # existirá; chamada direta acima
    # We already have admin_show_notifications defined earlier; call it:
    reload_all()
    if not notifications:
        print("Sem notificações.")
        return
    for n in notifications:
        print(f"[{n['timestamp']}] Usuário: {n['attempt_username']} / Nome: {n['attempt_name']} -> {n['message']}")

def hub_gestao(user):
    while True:
        print(f"\n--- HUB Gestão (ADM: {user['name']}) ---")
        print("1. Mostrar código de autorização")
        print("2. Ver notificações")
        print("3. Criar usuário (qualquer role)")
        print("4. Remover usuário")
        print("5. CRUD Pacientes")
        print("6. Gerenciar faturas")
        print("7. Ver agendamentos")
        print("8. Export CSV / Relatório")
        print("9. Inserir dados de exemplo")
        print("10. Lógica booleana / Tabelas")
        print("11. Simular fila")
        print("12. Ver logs (últimas linhas)")
        print("0. Sair")
        op = input("Escolha: ").strip()
        if op == "1":
            print(f"Código de autorização: {AUTH_CODE}")
            log_action("Gestão visualizou código de autorização")
        elif op == "2":
            admin_show_notifications()
        elif op == "3":
            admin_create_user()
        elif op == "4":
            admin_remove_user()
        elif op == "5":
            admin_crud_patients()
        elif op == "6":
            admin_manage_invoices_menu()
        elif op == "7":
            admin_manage_appointments()
        elif op == "8":
            exportar_csv(); gerar_relatorio_txt()
        elif op == "9":
            inserir_dados_exemplo = globals().get('inserir_dados_exemplo')
            if inserir_dados_exemplo:
                inserir_dados_exemplo()
        elif op == "10":
            print("1. Tabela Consulta Normal | 2. Tabela Emergência | 3. Contagem | 4. Caso prático | 0 Voltar")
            opc = input("Escolha: ").strip()
            if opc == "1": tabela_verdade_consulta()
            elif opc == "2": tabela_verdade_emergencia()
            elif opc == "3": contar_situacoes_regra()
            elif opc == "4": testar_caso_pratico()
            elif opc == "0": pass
        elif op == "11":
            simular_fila()
        elif op == "12":
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()[-50:]
                print("".join(lines))
        elif op == "0":
            break
        else:
            print("Inválido.")

# ------------------------
# INICIA / LOOP PRINCIPAL
# ------------------------
def initial_hub():
    reload_all()
    print("\n=== CLÍNICA VIDA+ ===")
    print("Qual é a sua função?")
    print("1. Sou Paciente")
    print("2. Sou Médico")
    print("3. Sou da Gestão")
    print("0. Sair")
    opt = input("Escolha: ").strip()
    if opt == "1":
        print("1. Login  2. Criar conta (paciente)  0. Voltar")
        o = input("Escolha: ").strip()
        if o == "1":
            user = autenticar("paciente")
            if user: hub_paciente(user)
        elif o == "2":
            criar_usuario("paciente")
    elif opt == "2":
        print("1. Login  2. Criar conta (médico)  0. Voltar")
        o = input("Escolha: ").strip()
        if o == "1":
            user = autenticar("medico")
            if user: hub_medico(user)
        elif o == "2":
            medico_create_hub()
    elif opt == "3":
        user = autenticar("gestao")
        if user: hub_gestao(user)
    elif opt == "0":
        return False
    else:
        print("Inválido.")
    return True

def main():
    reload_all()
    if not any(u['role']=="gestao" for u in users):
        users.append({"username":"admin","password":"admin","role":"gestao","name":"Administrador"})
        save_json(USERS_FILE, users)
        log_action("Usuário gestor padrão criado (admin/admin)")
        print("Usuário gestor padrão criado -> admin / admin")
    cont = True
    while cont:
        cont = initial_hub()
        input("\nPressione Enter para continuar...")

if __name__ == "__main__":
    main()
