#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clínica Vida+ — Versão com mensagens padronizadas e limpeza de duplicatas
Objetivos desta versão:
- Mensagens de aviso/ação padronizadas e claras
- Confirmações unificadas (S/N)
- Opção universal '0' como voltar/sair em menus
- Seleção por número para médicos/pacientes mantida
- Remoção de duplicatas/aliases óbvias e pequenas limpezas
Arquivos em dados/: users.json, pacientes.json, appointments.json, invoices.json, notifications.json, actions.log
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
# UTILITÁRIOS GERAIS / UI HELPERS
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

# UI helpers (substitua pelas novas versões abaixo)

def msg_info(text):
    print()                     # linha em branco antes
    print(f"[INFO] {text}")
    print()                     # linha em branco depois

def msg_warn(text):
    print()
    print(f"[AVISO] {text}")
    print()

def msg_err(text):
    print()
    print(f"[ERRO] {text}")
    print()

def msg_success(text):
    print()
    print(f"[OK] {text}")
    print()

def prompt_choice(prompt, allowed=None, default=None):
    """
    Prompt e validação simples. allowed=None aceita qualquer resposta.
    Retorna a string digitada (strip).
    """
    print()   # espaço extra antes do prompt para separar do bloco anterior
    resp = input(prompt).strip()
    if resp == "" and default is not None:
        return default
    if allowed is None:
        return resp
    if resp in allowed:
        return resp
    return resp

def confirm_yes_no(prompt):
    """
    Confirmação padronizada. Retorna True para 's'/'S', False para 'n'/'N'.
    Mostra instrução clara e aceita '0' como cancelar.
    """
    print()  # espaçamento antes do loop de confirmação
    while True:
        r = input(f"{prompt} (S/N) [0 para cancelar]: ").strip().lower()
        if r == "0" or r == "n":
            print()  # espaço após a resposta
            return False
        if r == "s":
            print()
            return True
        msg_warn("Resposta inválida. Digite 'S' para confirmar, 'N' para cancelar ou '0' para voltar.")

# ------------------------
# Carregamento inicial
# ------------------------
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
    msg_info(f"Cadastro de '{role}' em andamento. Digite o Nome/login abaixo! \nDigite 0 abaixo caso deseja cancelar o cadastro.")
    if username is None:
        username = input("Username: ").strip()
        if username == "0": 
            msg_warn("Criação de usuário cancelada."); return None
    if find_user(username):
        msg_err("Usuário já existe.")
        return None
    if role == "medico" and not skip_auth:
        code = input("Insira o código de autorização (peça à Gestão) ou 0 para voltar: ").strip()
        if code == "0":
            msg_warn("Operação cancelada pelo usuário."); return None
        if code != AUTH_CODE:
            msg_err("Código inválido. Você pode Notificar a Gestão em vez disso.")
            return None
    if password is None:
        password = input("Senha: ").strip()
        if password == "0":
            msg_warn("Operação cancelada."); return None
    if name is None:
        name = input("Nome completo: ").strip()
        if name == "0":
            msg_warn("Operação cancelada."); return None
    user = {"username": username, "password": password, "role": role, "name": name}
    users.append(user)
    save_json(USERS_FILE, users)
    log_action(f"Usuário criado: {username} ({role})")
    msg_success(f"Usuário '{username}' criado com sucesso.")
    if role == "paciente":
        if not next((p for p in patients if p.get("user") == username), None):
            p = {"nome": name, "idade": 0, "telefone": "Não informado", "user": username}
            patients.append(p)
            save_json(PATIENTS_FILE, patients)
            log_action(f"Paciente criado e vinculado ao user {username}")
    return user

def autenticar(role_expected):
    reload_all()
    msg_info(f"\nusername requerido, digite o seu username abaixo para acessar. \n função esperada: {role_expected}.")
    username = input("Username: ").strip()
    if username == "0": 
        msg_warn("Login cancelado."); return None
    password = input("\nSenha: ").strip()
    user = find_user(username)
    if not user or user.get("password") != password:
        msg_err("\nUsuário ou senha inválidos.")
        return None
    if user.get("role") != role_expected:
        msg_err(f"\nPermissão incorreta. Você é '{user.get('role')}', não '{role_expected}'.")
        return None
    log_action(f"\nUsername: {username} role={role_expected}")
    msg_success(f"\nLogin bem-sucedido. Bem-vindo(a), {user.get('name')}.")
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
        msg_warn("Nenhum cadastro vinculado ao seu usuário. Peça à gestão para vincular.")
        return
    msg_info("Seu cadastro (apenas visível por você):")
    print(f" Nome: {p.get('nome')}")
    print(f" Idade: {p.get('idade')}")
    print(f" Telefone: {p.get('telefone')}")
    print(f" Username vinculado: {p.get('user')}")

def listar_todos_pacientes_compacto():
    reload_all()
    if not patients:
        msg_info("Nenhum paciente cadastrado.")
        return
    print("\nLista de pacientes (número | nome | idade | telefone | username):")
    for i, p in enumerate(patients, start=1):
        print(f" {i}. {p.get('nome')} | {p.get('idade')} | {p.get('telefone')} | {p.get('user','-')}")

# ------------------------
# MÉDICOS — listagem para seleção numérica
# ------------------------
def listar_medicos_compacto():
    reload_all()
    medicos = [u for u in users if u.get("role") == "medico"]
    if not medicos:
        msg_info("Nenhum médico cadastrado.")
        return []
    print("\nMédicos disponíveis (número | nome | username):")
    for i, m in enumerate(medicos, start=1):
        print(f" {i}. {m.get('name')} | {m.get('username')}")
    return medicos

def escolher_medico_por_numero(prompt="Digite o número do médico (ou 0 para não atribuir): "):
    medicos = [u for u in users if u.get("role") == "medico"]
    if not medicos:
        msg_warn("Nenhum médico cadastrado; o agendamento ficará sem médico atribuído.")
        return None
    for i, m in enumerate(medicos, start=1):
        print(f" {i}. {m.get('name')} (username: {m.get('username')})")
    sel = input(prompt).strip()
    if sel == "0" or sel == "":
        return None
    try:
        n = int(sel)
        if 1 <= n <= len(medicos):
            return medicos[n-1]['username']
    except:
        pass
    msg_warn("Seleção inválida. Nenhum médico atribuído.")
    return None

# ------------------------
# AGENDAMENTOS
# ------------------------
def reload_appointments():
    global appointments
    appointments = load_json(APPTS_FILE)

def new_appt_id():
    reload_all()
    if not appointments:
        return 1
    return max(a.get("id",0) for a in appointments) + 1

def cadastrar_agendamento(patient_user, patient_name):
    reload_all()
    msg_info("Criando novo agendamento. '0' cancela a operação a qualquer momento.")
    doc_user = escolher_medico_por_numero("Digite o número do médico (ou 0 para não atribuir): ")
    dt = input("Data/Horário (ex: 2025-08-10 14:30): ").strip()
    if dt == "0":
        msg_warn("Criação de agendamento cancelada.")
        return
    notes = input("Observações (opcional, ENTER para nenhum): ").strip()
    appt = {"id": new_appt_id(), "patient_user": patient_user, "patient_name": patient_name,
            "doctor_user": doc_user, "datetime": dt, "status": "agendado", "notes": notes,
            "created_at": now_ts(), "created_by": patient_user}
    appointments.append(appt)
    save_json(APPTS_FILE, appointments)
    log_action(f"Agendamento criado ID {appt['id']} paciente {patient_user} médico {doc_user}")
    msg_success(f"Agendamento criado: ID {appt['id']}")

def listar_todos_agendamentos():
    reload_all()
    if not appointments:
        msg_info("Nenhum agendamento.")
        return
    print("\nAgendamentos (ID | paciente | username | médico_username | datetime | status):")
    for a in appointments:
        print(f" {a['id']} | {a['patient_name']} | {a.get('patient_user')} | {a.get('doctor_user') or '—'} | {a['datetime']} | {a['status']}")

def listar_meus_agendamentos(patient_user):
    reload_all()
    return [a for a in appointments if a.get("patient_user") == patient_user]

def paciente_agendamentos_menu(user):
    while True:
        print("\n--- Meus Agendamentos ---")
        print("\n1. Listar")
        print("2. Editar")
        print("3. Cancelar (marca)")
        print("4. Remover (apagar)")
        print("0. Voltar")
        op = input("Escolha: ").strip()
        if op == "1":
            meus = listar_meus_agendamentos(user['username'])
            if not meus:
                msg_info("Nenhum agendamento encontrado.")
            else:
                print("Seus agendamentos (ID | data | médico | status):")
                for a in meus:
                    print(f" {a['id']} | {a['datetime']} | {a.get('doctor_user') or '—'} | {a['status']}")
        elif op == "2":
            meus = listar_meus_agendamentos(user['username'])
            if not meus:
                msg_warn("Nenhum agendamento para editar.")
                continue
            for a in meus:
                print(f" {a['id']} - {a['datetime']} - Status: {a['status']} - Médico: {a.get('doctor_user') or '—'}")
            id_txt = input("Digite o ID para editar (ou 0 para voltar): ").strip()
            if id_txt == "0":
                continue
            try:
                id_int = int(id_txt)
                ap = next(a for a in appointments if a['id']==id_int and a['patient_user']==user['username'])
            except:
                msg_err("ID inválido ou não pertence a você."); continue
            msg_info("Selecione o novo médico (ou 0 para manter/nenhum).")
            novo_doc = escolher_medico_por_numero("Número do médico (ou 0): ")
            novo_dt = input(f"Novo Data/Horário [{ap['datetime']}] (ENTER = manter): ").strip() or ap['datetime']
            if novo_doc is None:
                novo_doc = ap.get('doctor_user')
            ap['datetime'] = novo_dt
            ap['doctor_user'] = novo_doc
            ap['last_modified_at'] = now_ts(); ap['last_modified_by'] = user['username']
            save_json(APPTS_FILE, appointments)
            log_action(f"Paciente {user['username']} editou agendamento {id_int}")
            msg_success("Agendamento atualizado.")
        elif op == "3":
            meus = listar_meus_agendamentos(user['username'])
            if not meus:
                msg_warn("Nenhum agendamento para cancelar.")
                continue
            for a in meus:
                print(f" {a['id']} - {a['datetime']} - Status: {a['status']}")
            id_txt = input("ID para cancelar (ou 0 voltar): ").strip()
            if id_txt == "0":
                continue
            try:
                id_int = int(id_txt)
                ap = next(a for a in appointments if a['id']==id_int and a['patient_user']==user['username'])
            except:
                msg_err("ID inválido."); continue
            if not confirm_yes_no("Tem certeza que deseja MARCAR este agendamento como CANCELADO?"):
                msg_warn("Operação cancelada.")
                continue
            ap['status'] = "cancelado"
            ap['last_modified_at'] = now_ts(); ap['last_modified_by'] = user['username']
            save_json(APPTS_FILE, appointments)
            log_action(f"Paciente {user['username']} cancelou agendamento {id_int}")
            msg_success("Agendamento marcado como CANCELADO.")
        elif op == "4":
            meus = listar_meus_agendamentos(user['username'])
            if not meus:
                msg_warn("Nenhum agendamento para remover.")
                continue
            for a in meus:
                print(f" {a['id']} - {a['datetime']} - Status: {a['status']}")
            id_txt = input("ID para remover definitivamente (ou 0 voltar): ").strip()
            if id_txt == "0":
                continue
            try:
                id_int = int(id_txt)
                ap = next(a for a in appointments if a['id']==id_int and a['patient_user']==user['username'])
            except:
                msg_err("ID inválido."); continue
            if not confirm_yes_no("ATENÇÃO: esta ação APAGA o agendamento permanentemente. Deseja continuar?"):
                msg_warn("Remoção cancelada.")
                continue
            appointments.remove(ap)
            save_json(APPTS_FILE, appointments)
            log_action(f"Paciente {user['username']} removeu agendamento {id_int}")
            msg_success("Agendamento REMOVIDO.")
        elif op == "0":
            break
        else:
            msg_warn("Opção inválida. Use os números do menu ou 0 para voltar.")

def ver_agendamentos_medico(doctor_user):
    reload_all()
    meus = [a for a in appointments if a.get("doctor_user") == doctor_user]
    if not meus:
        msg_info("Nenhum agendamento atribuído a você.")
        return
    print("\nSeus agendamentos (ID | paciente | data | status | obs):")
    for a in meus:
        print(f" {a['id']} | {a['patient_name']} | {a['datetime']} | {a['status']} | {a.get('notes','')}")

def editar_status_agendamento_medico(doctor_user):
    ver_agendamentos_medico(doctor_user)
    id_txt = input("ID do agendamento para alterar status (ou 0 voltar): ").strip()
    if id_txt == "0":
        return
    try:
        id_int = int(id_txt)
        ap = next(a for a in appointments if a['id']==id_int and a.get('doctor_user')==doctor_user)
    except:
        msg_err("ID inválido ou não é seu agendamento."); return
    novo = input("Novo status (agendado/confirmado/concluido/cancelado): ").strip().lower()
    if novo not in ("agendado","confirmado","concluido","cancelado"):
        msg_err("Status inválido."); return
    ap['status'] = novo
    ap['last_modified_at'] = now_ts(); ap['last_modified_by'] = doctor_user
    save_json(APPTS_FILE, appointments)
    log_action(f"Dr {doctor_user} atualizou status agendamento {id_int} -> {novo}")
    msg_success("Status atualizado.")

# ------------------------
# NOTIFICAÇÕES (gestão)
# ------------------------
def notify_management(attempt_username, attempt_name, message):
    reload_all()
    notif = {"timestamp": now_ts(), "attempt_username": attempt_username, "attempt_name": attempt_name, "message": message}
    notifications.append(notif)
    save_json(NOTIFS_FILE, notifications)
    log_action(f"Notificação criada: {attempt_username} / {attempt_name} -> {message}")
    msg_success("Notificação enviada para a gestão.")

def admin_show_notifications_list():
    reload_all()
    if not notifications:
        msg_info("Sem notificações.")
        return
    print("\nNotificações (timestamp | username solicitado | nome | mensagem):")
    for n in notifications:
        print(f" [{n['timestamp']}] {n['attempt_username']} | {n['attempt_name']} -> {n['message']}")

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
        msg_warn("Nenhum paciente cadastrado."); return None
    print("\nEscolha o paciente (número) ou 0 para cancelar:")
    for idx, p in enumerate(patients, start=1):
        print(f" {idx}. {p.get('nome')} (user: {p.get('user','')})")
    sel = input("Número do paciente: ").strip()
    if sel == "0" or sel == "":
        return None
    try:
        n = int(sel)
        if 1 <= n <= len(patients):
            return patients[n-1]
    except:
        pass
    msg_warn("Seleção inválida."); return None

def admin_create_invoice_for_patient():
    p = choose_patient_by_number()
    if not p:
        msg_warn("Operação cancelada.")
        return
    patient_user = p.get('user') or input("Paciente não tem username — digite username (ou 0 para cancelar): ").strip()
    if not patient_user or patient_user == "0":
        msg_warn("Operação cancelada."); return
    total_txt = input("Valor total (ex: 150.00): ").strip()
    try:
        total = float(total_txt.replace(",","." ))
    except:
        msg_err("Valor inválido."); return
    n_txt = input("Número de parcelas: ").strip()
    try:
        n = int(n_txt); assert n > 0
    except:
        msg_err("Parcelas inválidas."); return
    base = round(total / n, 2); remaining = total
    parcels = []
    for i in range(1, n+1):
        if i < n: amt = base
        else: amt = round(remaining, 2)
        parcels.append({"number": i, "amount": amt, "paid": False})
        remaining -= amt
    inv = {"id": new_invoice_id(), "patient_user": patient_user, "total": total, "parcels": parcels, "created_at": now_ts(), "created_by": "gestao"}
    invoices.append(inv); save_json(INVOICES_FILE, invoices)
    log_action(f"Gestão criou fatura {inv['id']} para {patient_user}")
    msg_success(f"Fatura criada ID {inv['id']} para {patient_user}")

def admin_list_invoices():
    reload_all()
    if not invoices:
        msg_info("Nenhuma fatura.")
        return
    print("\nFaturas (ID | paciente_user | total | criada):")
    for inv in invoices:
        print(f" {inv['id']} | {inv['patient_user']} | {inv['total']} | {inv['created_at']}")
        for p in inv['parcels']:
            print(f"    Parcela {p['number']}: {p['amount']} - {'PAGA' if p['paid'] else 'PENDENTE'}")

def admin_edit_invoice_parcel():
    admin_list_invoices()
    id_txt = input("ID da fatura (ou 0 para voltar): ").strip()
    if id_txt == "0": return
    try:
        id_int = int(id_txt); inv = next(i for i in invoices if i['id']==id_int)
    except:
        msg_err("ID inválido."); return
    for p in inv['parcels']:
        print(f" Parcela {p['number']}: {p['amount']} - {'PAGA' if p['paid'] else 'PENDENTE'}")
    num_txt = input("Nº da parcela para alternar paga/não paga (ou 0 voltar): ").strip()
    if num_txt == "0": return
    try:
        num = int(num_txt); parc = next(p for p in inv['parcels'] if p['number']==num)
    except:
        msg_err("Parcela inválida."); return
    parc['paid'] = not parc['paid']; save_json(INVOICES_FILE, invoices)
    log_action(f"Gestão alternou parcela {num} da fatura {id_int} -> {'PAGA' if parc['paid'] else 'PENDENTE'}")
    msg_success("Alteração salva.")

def admin_remove_invoice():
    admin_list_invoices()
    id_txt = input("ID para remover (ou 0 voltar): ").strip()
    if id_txt == "0": return
    try:
        id_int = int(id_txt); inv = next(i for i in invoices if i['id']==id_int)
        if not confirm_yes_no(f"Confirmar remoção da fatura {id_int}?"):
            msg_warn("Remoção cancelada."); return
        invoices.remove(inv); save_json(INVOICES_FILE, invoices); log_action(f"Gestão removeu fatura {id_int}"); msg_success("Removido.")
    except:
        msg_err("Inválido.")

def patient_view_my_invoices_menu(user):
    while True:
        print("\n--- Minhas Faturas ---")
        print("\n1. Ver minhas faturas")
        print("0. Voltar")
        op = input("Escolha: ").strip()
        if op == "1":
            reload_all()
            my = [inv for inv in invoices if inv.get("patient_user") == user['username']]
            if not my:
                msg_info("Nenhuma fatura encontrada para você.")
            else:
                for inv in my:
                    print(f"\nID {inv['id']} - Total {inv['total']} - Criada {inv['created_at']}")
                    for p in inv['parcels']:
                        print(f"   Parcela {p['number']}: {p['amount']} - {'PAGA' if p['paid'] else 'PENDENTE'}")
                    pend = sum(1 for p in inv['parcels'] if not p['paid'])
                    print(f"   Parcelas pendentes: {pend}")
        elif op == "0":
            break
        else:
            msg_warn("Opção inválida.")

def medico_consultar_faturas():
    reload_all()
    uname = input("Username do paciente (ou 0 voltar): ").strip()
    if uname == "0" or uname == "":
        return
    my = [inv for inv in invoices if inv.get("patient_user") == uname]
    if not my:
        msg_info("Nenhuma fatura para esse paciente.")
    else:
        for inv in my:
            print(f"\nID {inv['id']} - Total {inv['total']} - Criada {inv['created_at']}")
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
    msg_info(f"Consulta Normal atende em {total_cons} de 16 situações.")
    msg_info(f"Emergência atende em {total_emerg} de 16 situações.")

def testar_caso_pratico():
    A=False; B=True; C=True; D=False
    cons, emerg = avaliar_regras(A,B,C,D)
    msg_info("Caso prático: A=F B=V C=V D=F")
    print(f" Consulta Normal: {bool_to_vf(cons)} -> {'ATENDE' if cons else 'NÃO ATENDE'}")
    print(f" Emergência: {bool_to_vf(emerg)} -> {'ATENDE' if emerg else 'NÃO ATENDE'}")

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
    msg_success(f"CSV exportado: {filename}")

def gerar_relatorio_txt(path=REPORT_FILE):
    reload_all()
    if not patients:
        msg_info("Sem pacientes.")
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
    msg_success(f"Relatório gerado: {path}")

def simular_fila():
    fila = deque()
    msg_info("Simulação de fila FIFO — digite 0 para cancelar qualquer cadastro.")
    for i in range(1,4):
        nome = input(f"Nome paciente {i}: ").strip()
        if nome == "0": msg_warn("Simulação cancelada."); return
        cpf = input(f"CPF paciente {i}: ").strip()
        if cpf == "0": msg_warn("Simulação cancelada."); return
        fila.append({"nome": nome, "cpf": cpf})
    print("\nFila atual:")
    for idx,p in enumerate(fila, start=1):
        print(f" {idx}. {p['nome']} | {p['cpf']}")
    atendido = fila.popleft()
    msg_success(f"Atendido: {atendido['nome']} | {atendido['cpf']}")
    if fila:
        print("\nRestantes:")
        for idx,p in enumerate(fila, start=1):
            print(f" {idx}. {p['nome']} | {p['cpf']}")
    else:
        msg_info("Fila vazia.")

# ------------------------
# HUBs (menus) — padronizando 0 como voltar/sair
# ------------------------
def medico_create_hub():
    while True:
        print("\n--- Criação de conta (Médico) ---")
        print("\n1. Inserir código de autorização")
        print("2. Notificar a gestão (envia aviso, não cria o usuário automaticamente)")
        print("0. Voltar")
        opt = input("Escolha: ").strip()
        if opt == "1":
            code = input("Código (ou 0 voltar): ").strip()
            if code == "0":
                continue
            if code != AUTH_CODE:
                msg_err("Código inválido."); continue
            username = input("Username desejado: ").strip()
            if username == "0": continue
            if find_user(username):
                msg_err("Username já existe."); continue
            password = input("Senha: ").strip()
            if password == "0": continue
            name = input("Nome completo: ").strip()
            if name == "0": continue
            criar_usuario("medico", username=username, password=password, name=name, skip_auth=True)
        elif opt == "2":
            attempted_username = input("Username desejado: ").strip()
            if attempted_username == "0": continue
            attempted_name = input("Nome completo: ").strip()
            if attempted_name == "0": continue
            message = input("Mensagem para a gestão: ").strip()
            if message == "0": continue
            notify_management(attempted_username, attempted_name, message)
        elif opt == "0":
            break
        else:
            msg_warn("Opção inválida. Use números do menu ou 0 para voltar.")

def hub_paciente(user):
    while True:
        print(f"\n--- HUB Paciente ({user['name']}) ---")
        print("\n1. Ver meu cadastro")
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
                msg_warn("Nenhum cadastro vinculado. Peça à gestão.")
                continue
            msg_info("Edite apenas o campo que deseja. Enter mantém o valor atual. Digite 0 para cancelar.")
            novo = input(f"Novo nome [{p['nome']}]: ").strip()
            if novo == "0": msg_warn("Edição cancelada."); continue
            novo = novo or p['nome']
            idade_txt = input(f"Nova idade [{p['idade']}]: ").strip()
            if idade_txt == "0": msg_warn("Edição cancelada."); continue
            idade = validar_idade(idade_txt) if idade_txt else p['idade']
            tel_in = input(f"Novo telefone [{p['telefone']}]: ").strip()
            if tel_in == "0": msg_warn("Edição cancelada."); continue
            tel = format_telefone(tel_in) if tel_in and validar_telefone_raw(tel_in) else (tel_in or p['telefone'])
            p['nome'] = novo; p['idade'] = idade; p['telefone'] = tel
            p['last_modified_at'] = now_ts(); p['last_modified_by'] = user['username']
            save_json(PATIENTS_FILE, patients)
            log_action(f"Paciente {user['username']} atualizou seu cadastro")
            msg_success("Cadastro atualizado.")
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
            msg_warn("Opção inválida. Use números do menu ou 0 para sair/voltar.")

def hub_medico(user):
    while True:
        print(f"\n--- Agendamentos de Serviços ({user['name']}) ---")
        print("\n1. Ver meus agendamentos")
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
            msg_warn("Opção inválida.")

def admin_create_user():
    role = input("Role (paciente/medico/gestao) ou 0 para voltar: ").strip().lower()
    if role == "0": return
    if role not in ("paciente","medico","gestao"):
        msg_err("Role inválida."); return
    if role == "medico":
        criar_usuario("medico", skip_auth=True)
    else:
        criar_usuario(role)

def admin_remove_user():
    reload_all()
    print("\nUsuários (número | username | name | role):")
    for i,u in enumerate(users, start=1):
        print(f" {i}. {u['username']} | {u['name']} | {u['role']}")
    idx = input("Número do usuário a remover (ou 0 voltar): ").strip()
    if idx == "0": return
    try:
        i = int(idx)-1; u = users.pop(i); save_json(USERS_FILE, users); log_action(f"Gestão removeu usuário {u['username']}"); msg_success("Usuário removido.")
    except:
        msg_err("Índice inválido.")

def admin_crud_patients():
    while True:
        print("\n-- CRUD Pacientes --")
        print("\n1. Listar")
        print("2. Criar")
        print("3. Editar")
        print("4. Remover")
        print("0. Voltar")
        op = input("Escolha: ").strip()
        if op == "1":
            listar_todos_pacientes_compacto()
        elif op == "2":
            nome = input("Nome: ").strip()
            if nome == "0": msg_warn("Operação cancelada."); continue
            idade = validar_idade(input("Idade: ").strip()) or 0
            tel = input("Telefone: ").strip() or "Não informado"; 
            userlink = input("Username vinculado (opcional, 0 p/nenhum): ").strip() or None
            if userlink == "0": userlink = None
            p = {"nome": nome, "idade": idade, "telefone": tel}
            if userlink: p["user"] = userlink
            patients.append(p); save_json(PATIENTS_FILE, patients); log_action(f"Gestão criou paciente {nome}"); msg_success("Paciente criado.")
        elif op == "3":
            listar_todos_pacientes_compacto(); idx = input("Número do paciente editar (ou 0 voltar): ").strip()
            if idx == "0": continue
            try:
                i = int(idx)-1; p = patients[i]
            except: msg_err("Inválido"); continue
            p['nome'] = input(f"Nome [{p['nome']}]: ").strip() or p['nome']
            idade_txt = input(f"Idade [{p['idade']}]: ").strip(); p['idade'] = validar_idade(idade_txt) if idade_txt else p['idade']
            p['telefone'] = input(f"Telefone [{p['telefone']}]: ").strip() or p['telefone']
            p['user'] = input(f"Username vinculado [{p.get('user','')}]: ").strip() or p.get('user')
            save_json(PATIENTS_FILE, patients); log_action(f"Gestão editou paciente {p['nome']}"); msg_success("Paciente atualizado.")
        elif op == "4":
            listar_todos_pacientes_compacto(); idx = input("Número do paciente remover (ou 0 voltar): ").strip()
            if idx == "0": continue
            try:
                i = int(idx)-1; p = patients.pop(i); save_json(PATIENTS_FILE, patients); log_action(f"Gestão removeu paciente {p['nome']}"); msg_success("Removido.")
            except: msg_err("Inválido.")
        elif op == "0": break
        else: msg_warn("Inválido.")

def admin_manage_invoices_menu():
    while True:
        print("\n-- Gestão Faturas --")
        print("\n1. Listar")
        print("2. Criar")
        print("3. Editar parcela:")
        print("4. Remover")
        print("0. Voltar")
        op = input("Escolha: ").strip()
        if op == "1": admin_list_invoices()
        elif op == "2": admin_create_invoice_for_patient()
        elif op == "3": admin_edit_invoice_parcel()
        elif op == "4": admin_remove_invoice()
        elif op == "0": break
        else: msg_warn("Inválido.")

def admin_manage_appointments():
    reload_all()
    if not appointments:
        msg_info("Nenhum agendamento.")
        return
    print("\nAgendamentos gerenciais \n(ID | paciente | user | médico | datetime | status):")
    for a in appointments:
        print(f" {a['id']} | {a['patient_name']} | {a.get('patient_user')} | {a.get('doctor_user') or '—'} | {a['datetime']} | {a['status']}")

def hub_gestao(user):
    while True:
        print(f"\n--- HUB Gestão (ADM: {user['name']}) ---")
        print("\n1. Mostrar código de autorização")
        print("2. Ver notificações")
        print("3. Criar usuário (qualquer role)")
        print("4. Remover usuário")
        print("5. CRUD Pacientes")
        print("6. Gerenciar faturas")
        print("7. Ver agendamentos")
        print("8. Export CSV / Relatório")
        print("9. Inserir dados de exemplo")
        print("10.1 Lógica booleana / Tabelas")
        print("11. Simular fila")
        print("12. Ver logs (últimas linhas)")
        print("0. Sair")
        op = input("Escolha: ").strip()
        if op == "1":
            print(f"\nCódigo de autorização: {AUTH_CODE}")
            log_action("\nGestão visualizou código de autorização")
        elif op == "2":
            admin_show_notifications_list()
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
            msg_info("Inserindo dados de exemplo...")
            exemplos = [
                {"nome": "João Silva", "idade": 45, "telefone": "(11) 99999-9999", "user": "joaos"},
                {"nome": "Maria Lima", "idade": 32, "telefone": "(11) 98888-8888", "user": "marial"},
                {"nome": "Pedro Souza", "idade": 60, "telefone": "(11) 97777-7777", "user": "pedros"},
                {"nome": "Nicolas Telas", "idade": 19, "telefone": "(11) 96666-6666", "user": "Nicolas"},
                {"nome": "Nastia Nestle", "idade": 22, "telefone": "(11) 95555-5555", "user": "Nastia"},
                {"nome": "Rennato Cariane", "idade": 54, "telefone": "(11) 94444-4444", "user": "Rennato"},
                {"nome": "Ramon Dino", "idade": 49, "telefone": "(11) 93333-3333", "user": "Ramon"},
            ]
            patients.extend(exemplos); save_json(PATIENTS_FILE, patients); log_action("Inseridos dados exemplo pelo gestor"); msg_success("Dados de exemplo inseridos.")
        elif op == "10":
            print("1. Tabela Consulta Normal | 2. Tabela Emergência | 3. Contagem | 4. Caso prático | 0 Voltar")
            opc = input("Escolha: ").strip()
            if opc == "1": tabela_verdade_consulta()
            elif opc == "2": tabela_verdade_emergencia()
            elif opc == "3": contar_situacoes_regra()
            elif opc == "4": testar_caso_pratico()
        elif op == "11":
            simular_fila()
        elif op == "12":
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()[-50:]
                print("".join(lines))
        elif op == "0":
            break
        else: msg_warn("Inválido.")

# ------------------------
# Inicial / Main loop
# ------------------------
def initial_hub():
    reload_all()
    print("\n=== CLÍNICA VIDA+ ===")
    print("\nQual é a sua função?")
    print("\n1. Sou Paciente")
    print("2. Sou Médico")
    print("3. Sou da Gestão")
    print("0. Sair")
    opt = input("Escolha: ").strip()
    if opt == "1":
        print("\n1. Login")
        print("2. Criar conta (paciente)")
        print("0. Voltar")
        o = input("Escolha: ").strip()
        if o == "1":
            user = autenticar("paciente")
            if user: hub_paciente(user)
        elif o == "2":
            criar_usuario("paciente")
    elif opt == "2":
        print("\n1. Login  \n2. Criar conta (médico)  \n0. Voltar")
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
        msg_warn("Inválido.")
    return True

def main():
    reload_all()
    if not any(u['role']=="gestao" for u in users):
        users.append({"username":"admin","password":"admin","role":"gestao","name":"Administrador"})
        save_json(USERS_FILE, users); log_action("Usuário gestor padrão criado (admin/admin)")
        msg_info("\nUsuário gestor padrão criado -> admin / admin")
    cont = True
    while cont:
        cont = initial_hub()
        input("\nPressione Enter para continuar...")

if __name__ == "__main__":
    main()