#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clínica Vida+ — Sistema revisto
Novas features:
- Paciente: ver apenas seu cadastro; ver/editar/cancelar/remover agendamento; ver faturas.
- Médico: pode ver todos pacientes (opção), ver/editar agendamentos, consultar faturas.
- Gestão: pode ver todas notificações e código de autorização; pode criar médicos com código.
- Fluxo criação médico: antes do código aparece HUB com opção "Notificar a gestão" que salva em notifications.json.
- Correção: exclusão/edição de agendamentos agora salva corretamente (usando reload_data() e save_json()).
Arquivos em dados/: users.json, pacientes.json, appointments.json, invoices.json, notifications.json, actions.log, pacientes.csv, relatorio_estatisticas.txt
"""

import os, json, csv, re, difflib
from datetime import datetime
from collections import deque

# -------------------------
# Configuração / arquivos
# -------------------------
DATA_DIR = "dados"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
PATIENTS_FILE = os.path.join(DATA_DIR, "pacientes.json")
APPTS_FILE = os.path.join(DATA_DIR, "appointments.json")
INVOICES_FILE = os.path.join(DATA_DIR, "invoices.json")
NOTIFS_FILE = os.path.join(DATA_DIR, "notifications.json")
CSV_FILE = os.path.join(DATA_DIR, "pacientes.csv")
REPORT_FILE = os.path.join(DATA_DIR, "relatorio_estatisticas.txt")
LOG_FILE = os.path.join(DATA_DIR, "actions.log")

# Código que a gestão mostra para autorizar criação de médicos
AUTH_CODE = "GESTAO-2025-CODE"

# Inicializa arquivos vazios quando necessário
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

# -------------------------
# Utilitários
# -------------------------
def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
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

# Carrega tudo inicialmente
reload_all()

# -------------------------
# Validações básicas
# -------------------------
def only_digits(s): return re.sub(r"\D", "", s or "")

def validar_idade(v):
    try:
        i = int(v); return i if i>=0 else None
    except: return None

def validar_telefone_raw(tel):
    d = only_digits(tel)
    return len(d) in (10,11)

def format_telefone(tel):
    d = only_digits(tel)
    if len(d) < 10: return tel.strip()
    ddd = d[:2]; rest = d[2:]
    if len(rest)==8: return f"({ddd}) {rest[:4]}-{rest[4:]}"
    if len(rest)==9: return f"({ddd}) {rest[:5]}-{rest[5:]}"
    last9 = rest[-9:]; return f"({ddd}) {last9[:5]}-{last9[5:]}"

# -------------------------
# Usuários / autenticação
# -------------------------
def find_user(username):
    reload_all()
    return next((u for u in users if u['username']==username), None)

def criar_usuario(role, username=None, password=None, name=None, require_auth_for_medico=True):
    """
    Cria usuário. If role == 'medico' we will require AUTH_CODE but the flow has special HUB.
    Note: criar_usuario is a low-level helper — avoid calling it directly for medico registration (use medico_hub_create).
    """
    reload_all()
    if username is None:
        username = input("Username: ").strip()
    if find_user(username):
        print("Usuário já existe.")
        return None
    if password is None:
        password = input("Senha: ").strip()
    if name is None:
        name = input("Nome completo: ").strip()
    user = {"username": username, "password": password, "role": role, "name": name}
    users.append(user)
    save_json(USERS_FILE, users)
    log(f"Usuário criado: {username} ({role})")
    # vincula paciente quando role == paciente
    if role == "paciente":
        # cria registro de paciente vinculado se não existir
        if not next((p for p in patients if p.get("user")==username), None):
            p = {"nome": name, "idade": 0, "telefone": "Não informado", "user": username}
            patients.append(p)
            save_json(PATIENTS_FILE, patients)
            log(f"Paciente criado e vinculado ao user {username}")
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
    log(f"Login: {username} role={role_expected}")
    return user

# -------------------------
# Notificações (para a gestão)
# -------------------------
def notify_management(attempt_username, attempt_name, message):
    reload_all()
    notif = {"timestamp": now_ts(), "attempt_username": attempt_username, "attempt_name": attempt_name, "message": message}
    notifications.append(notif)
    save_json(NOTIFS_FILE, notifications)
    log(f"Notificação criada por tentativa: {attempt_username} / {attempt_name} -> {message}")

def admin_show_notifications():
    reload_all()
    if not notifications:
        print("Sem notificações.")
        return
    print("\n=== Notificações (Gestão) ===")
    for n in notifications:
        print(f"[{n['timestamp']}] Usuário: {n['attempt_username']} / Nome: {n['attempt_name']} -> {n['message']}")

# -------------------------
# Pacientes (visualizar só o próprio)
# -------------------------
def find_patient_by_user(username):
    reload_all()
    return next((p for p in patients if p.get("user")==username), None)

def patient_view_own(user):
    """Mostra apenas o cadastro vinculado ao user"""
    p = find_patient_by_user(user['username'])
    if not p:
        print("Nenhum cadastro vinculado. Peça à gestão para vincular.")
        return
    print("\n--- Meu cadastro ---")
    print(f"Nome: {p.get('nome')}")
    print(f"Idade: {p.get('idade')}")
    print(f"Telefone: {p.get('telefone')}")
    print(f"Username vinculado: {p.get('user')}")

# Médicos e Gestão podem ver todos os pacientes
def list_all_patients():
    reload_all()
    if not patients:
        print("Nenhum paciente cadastrado.")
        return
    for i,p in enumerate(patients, start=1):
        print(f"{i}. {p.get('nome')} | {p.get('idade')} | {p.get('telefone')} | user: {p.get('user','-')}")

# -------------------------
# Agendamentos (corrigidos para edição e exclusão)
# -------------------------
def new_appt_id():
    reload_all()
    if not appointments: return 1
    return max(a.get("id",0) for a in appointments) + 1

def agendar_consulta(patient_user, patient_name):
    reload_all()
    doctor_user = input("Username do médico (opcional): ").strip() or None
    dt = input("Data/Horário (ex: 2025-08-10 14:30): ").strip()
    notes = input("Observações (opcional): ").strip()
    appt = {"id": new_appt_id(), "patient_user": patient_user, "patient_name": patient_name,
            "doctor_user": doctor_user, "datetime": dt, "status": "agendado", "notes": notes}
    appointments.append(appt)
    save_json(APPTS_FILE, appointments)
    log(f"Agendamento criado ID {appt['id']} paciente {patient_user}")
    print(f"Agendamento criado: ID {appt['id']}")

def list_my_appointments(patient_user):
    reload_all()
    return [a for a in appointments if a.get("patient_user")==patient_user]

def paciente_agendamentos_menu(user):
    """
    Submenu paciente com Listar / Editar / Cancelar / Remover
    EDITAR salva corretamente; REMOVER deleta o agendamento da lista e salva (bug corrigido).
    """
    while True:
        print("\n--- Meus Agendamentos ---")
        print("1. Listar")
        print("2. Editar agendamento (alterar data/médico)")
        print("3. Cancelar agendamento (marca 'cancelado')")
        print("4. Remover agendamento (apaga definitivamente)")
        print("5. Voltar")
        op = input("Escolha: ").strip()
        if op == "1":
            meus = list_my_appointments(user['username'])
            if not meus:
                print("Nenhum agendamento.")
            else:
                for a in meus:
                    print(f"ID {a['id']} - {a['datetime']} - Médico: {a.get('doctor_user') or 'Não atribuído'} - Status: {a['status']}")
        elif op == "2":
            meus = list_my_appointments(user['username'])
            if not meus:
                print("Nenhum agendamento para editar.")
                continue
            for a in meus:
                print(f"ID {a['id']} - {a['datetime']} - Status: {a['status']}")
            id_txt = input("Digite o ID do agendamento a editar: ").strip()
            try:
                id_int = int(id_txt)
                ap = next(a for a in appointments if a['id']==id_int and a['patient_user']==user['username'])
            except Exception:
                print("ID inválido.")
                continue
            novo_dt = input(f"Novo Data/Horário [{ap['datetime']}]: ").strip() or ap['datetime']
            novo_doc = input(f"Novo médico (username) [{ap.get('doctor_user') or ''}]: ").strip() or ap.get('doctor_user')
            ap['datetime'] = novo_dt
            ap['doctor_user'] = novo_doc
            save_json(APPTS_FILE, appointments)   # salva após edição (corrigido)
            log(f"Paciente {user['username']} editou agendamento {id_int}")
            print("Agendamento atualizado.")
        elif op == "3":
            meus = list_my_appointments(user['username'])
            if not meus:
                print("Nenhum agendamento para cancelar.")
                continue
            for a in meus:
                print(f"ID {a['id']} - {a['datetime']} - Status: {a['status']}")
            id_txt = input("Digite o ID do agendamento a cancelar: ").strip()
            try:
                id_int = int(id_txt)
                ap = next(a for a in appointments if a['id']==id_int and a['patient_user']==user['username'])
            except Exception:
                print("ID inválido.")
                continue
            ap['status'] = "cancelado"
            save_json(APPTS_FILE, appointments)
            log(f"Paciente {user['username']} cancelou agendamento {id_int}")
            print("Agendamento marcado como CANCELADO.")
        elif op == "4":
            meus = list_my_appointments(user['username'])
            if not meus:
                print("Nenhum agendamento para remover.")
                continue
            for a in meus:
                print(f"ID {a['id']} - {a['datetime']} - Status: {a['status']}")
            id_txt = input("Digite o ID do agendamento a remover definitivamente: ").strip()
            try:
                id_int = int(id_txt)
                ap = next(a for a in appointments if a['id']==id_int and a['patient_user']==user['username'])
            except Exception:
                print("ID inválido.")
                continue
            # remover da lista e salvar — aqui estava o problema antes: agora garantimos reload e save
            appointments.remove(ap)
            save_json(APPTS_FILE, appointments)
            log(f"Paciente {user['username']} removeu agendamento {id_int}")
            print("Agendamento REMOVIDO (excluído).")
        elif op == "5":
            break
        else:
            print("Opção inválida.")

# Médicos: ver/editar status; podem também ver todos pacientes
def ver_agendamentos_medico(doctor_user):
    reload_all()
    meus = [a for a in appointments if a.get("doctor_user")==doctor_user]
    if not meus:
        print("Nenhum agendamento para você.")
        return
    for a in meus:
        print(f"ID {a['id']} - Paciente: {a['patient_name']} - {a['datetime']} - Status: {a['status']} - Obs: {a.get('notes','')}")

def editar_status_agendamento_medico(doctor_user):
    ver_agendamentos_medico(doctor_user)
    id_txt = input("ID do agendamento para alterar status: ").strip()
    try:
        id_int = int(id_txt)
        ap = next(a for a in appointments if a['id']==id_int and a.get('doctor_user')==doctor_user)
    except Exception:
        print("ID inválido ou não é seu agendamento.")
        return
    novo = input("Novo status (agendado/confirmado/concluido/cancelado): ").strip().lower()
    if novo not in ("agendado","confirmado","concluido","cancelado"):
        print("Status inválido.")
        return
    ap['status'] = novo
    save_json(APPTS_FILE, appointments)
    log(f"Dr {doctor_user} atualizou status do agendamento {id_int} -> {novo}")
    print("Status atualizado.")

# -------------------------
# Fluxo de criação de médico com HUB -> Notificação
# -------------------------
def medico_create_hub():
    """
    Antes de pedir código, mostra HUB:
    1) Inserir código (tenta criar conta se código válido)
    2) Notificar a gestão (cria notificação com timestamp e nome)
    3) Voltar
    """
    print("\n--- Criação de Conta (Médico) ---")
    print("1. Inserir código de autorização")
    print("2. Notificar a gestão (solicitação automática será salva)")
    print("3. Voltar")
    opt = input("Escolha: ").strip()
    if opt == "1":
        code = input("Digite o código de autorização (fornecido pela gestão): ").strip()
        if code != AUTH_CODE:
            print("Código inválido. Se quiser, notifique a gestão para solicitar autorização.")
            return
        # se válido, pedir username/password/name e criar
        username = input("Username desejado: ").strip()
        if find_user(username):
            print("Username já existe.")
            return
        password = input("Senha: ").strip()
        name = input("Nome completo: ").strip()
        criar_usuario("medico", username=username, password=password, name=name, require_auth_for_medico=False)
        print("Conta médica criada com sucesso.")
    elif opt == "2":
        # Notificar gestão: pede nome do solicitante (pode ser o nome do médico)
        attempted_username = input("Username desejado (para registro na notificação): ").strip()
        attempted_name = input("Nome completo (para notificação): ").strip()
        message = input("Mensagem para a gestão (ex: Solicito código para criar conta médica): ").strip()
        notify_management(attempted_username, attempted_name, message)
        print("Notificação enviada à gestão. A gestão verá este aviso no hub.")
    else:
        return

# -------------------------
# Faturas (resumo: paciente vê só suas faturas; médico consulta; gestão edita)
# -------------------------
def new_invoice_id():
    reload_all()
    if not invoices: return 1
    return max(i.get("id",0) for i in invoices)+1

def create_invoice(patient_user):
    reload_all()
    total_txt = input("Valor total: ").strip()
    try:
        total = float(total_txt.replace(",","." ))
    except:
        print("Valor inválido."); return
    n_txt = input("Número de parcelas: ").strip()
    try:
        n = int(n_txt); assert n>0
    except:
        print("Parcelas inválidas."); return
    base = round(total / n, 2)
    parcels = []
    remain = total
    for i in range(1, n+1):
        if i < n:
            amt = base
        else:
            amt = round(remain, 2)
        parcels.append({"number": i, "amount": amt, "paid": False})
        remain -= amt
    inv = {"id": new_invoice_id(), "patient_user": patient_user, "total": total, "parcels": parcels, "created_at": now_ts()}
    invoices.append(inv)
    save_json(INVOICES_FILE, invoices)
    log(f"Fatura criada ID {inv['id']} para {patient_user}")
    print(f"Fatura criada ID {inv['id']}")

def view_invoices_patient(patient_user):
    reload_all()
    my = [inv for inv in invoices if inv.get("patient_user")==patient_user]
    if not my:
        print("Nenhuma fatura.")
        return
    for inv in my:
        print(f"ID {inv['id']} - Total {inv['total']} - Criada {inv['created_at']}")
        for p in inv['parcels']:
            print(f"  Parcela {p['number']}: {p['amount']} - {'PAGA' if p['paid'] else 'PENDENTE'}")
        pend = sum(1 for p in inv['parcels'] if not p['paid'])
        print(f"  Parcelas pendentes: {pend}")

def medico_consultar_faturas():
    reload_all()
    uname = input("Username do paciente: ").strip()
    view_invoices_patient(uname)

# Gestão: editar parcela (marcar como paga)
def admin_edit_invoice():
    reload_all()
    if not invoices:
        print("Sem faturas.")
        return
    for inv in invoices:
        print(f"ID {inv['id']} - paciente {inv['patient_user']} - total {inv['total']}")
    id_txt = input("ID da fatura: ").strip()
    try:
        id_int = int(id_txt)
        inv = next(i for i in invoices if i['id']==id_int)
    except:
        print("ID inválido"); return
    for p in inv['parcels']:
        print(f"Parcela {p['number']}: {p['amount']} - {'PAGA' if p['paid'] else 'PENDENTE'}")
    num_txt = input("Nº da parcela para alternar paga/não paga: ").strip()
    try:
        num = int(num_txt)
        parc = next(p for p in inv['parcels'] if p['number']==num)
    except:
        print("Parcela inválida"); return
    parc['paid'] = not parc['paid']
    save_json(INVOICES_FILE, invoices)
    log(f"Admin alternou parcela {num} da fatura {id_int} -> {'PAGA' if parc['paid'] else 'PENDENTE'}")
    print("Alteração salva.")

# -------------------------
# Hubs (Paciente / Médico / Gestão)
# -------------------------
def hub_paciente(user):
    while True:
        print(f"\n--- HUB Paciente: {user['name']} ---")
        print("1. Ver meu cadastro")
        print("2. Agendar consulta")
        print("3. Meus agendamentos (listar/editar/cancelar/remover)")
        print("4. Minhas faturas")
        print("5. Sair do HUB")
        op = input("Escolha: ").strip()
        if op == "1":
            patient_view_own(user)
        elif op == "2":
            # garante paciente vinculado
            if not find_patient_by_user(user['username']):
                create_patient_for_user = lambda u,name: patients.append({"nome": name, "idade":0, "telefone":"Não informado", "user":u})
                if not find_patient_by_user(user['username']):
                    patients.append({"nome": user['name'], "idade":0, "telefone":"Não informado", "user": user['username']})
                    save_json(PATIENTS_FILE, patients)
            agendar_consulta(user['username'], user['name'])
        elif op == "3":
            paciente_agendamentos_menu(user)
        elif op == "4":
            patient_view_my_invoices_menu(user)
        elif op == "5":
            break
        else:
            print("Inválido.")

def hub_medico(user):
    while True:
        print(f"\n--- HUB Médico: {user['name']} ---")
        print("1. Ver meus agendamentos")
        print("2. Editar status de agendamento")
        print("3. Consultar faturas de paciente")
        print("4. Ver todos os pacientes")
        print("5. Sair do HUB")
        op = input("Escolha: ").strip()
        if op == "1":
            ver_agendamentos_medico(user['username'])
        elif op == "2":
            editar_status_agendamento_medico(user['username'])
        elif op == "3":
            medico_consultar_faturas()
        elif op == "4":
            list_all_patients()   # médico tem permissão de ver todos
        elif op == "5":
            break
        else:
            print("Inválido.")

def hub_gestao(user):
    while True:
        print(f"\n--- HUB Gestão (ADM: {user['name']}) ---")
        print("1. Mostrar código de autorização (para médicos)")
        print("2. Ver todas notificações")
        print("3. Criar usuário (qualquer role)")
        print("4. Remover usuário")
        print("5. CRUD Pacientes")
        print("6. Gerenciar faturas")
        print("7. Ver/gerenciar agendamentos")
        print("8. Exportar CSV / Gerar relatório")
        print("9. Simular fila")
        print("10. Sair do HUB")
        op = input("Escolha: ").strip()
        if op == "1":
            print(f"Código: {AUTH_CODE}")
            log("Gestão visualizou código de autorização")
        elif op == "2":
            admin_show_notifications()
        elif op == "3":
            admin_create_user()
        elif op == "4":
            admin_remove_user()
        elif op == "5":
            admin_crud_patients()
        elif op == "6":
            admin_manage_invoices()
        elif op == "7":
            admin_manage_appointments()
        elif op == "8":
            export_csv()
            gerar_relatorio_txt()
        elif op == "9":
            simular_fila()
        elif op == "10":
            break
        else:
            print("Inválido.")

# Funções auxiliares de gestão (resumos)
def admin_create_user():
    role = input("Role (paciente/medico/gestao): ").strip().lower()
    if role not in ("paciente","medico","gestao"):
        print("Role inválida."); return
    # se for medico, presença do codigo (gestão cria sem código)
    if role == "medico":
        # como gestão está criando, não pedimos código
        criar_usuario("medico")
    else:
        criar_usuario(role)

def admin_remove_user():
    reload_all()
    for i,u in enumerate(users, start=1):
        print(f"{i}. {u['username']} | {u['name']} | {u['role']}")
    idx = input("Digite número do usuário a remover: ").strip()
    try:
        i = int(idx)-1
        u = users.pop(i)
        save_json(USERS_FILE, users)
        log(f"Gestão removeu usuário {u['username']}")
        print("Usuário removido.")
    except:
        print("Índice inválido.")

def admin_crud_patients():
    while True:
        print("\n-- CRUD Pacientes (Gestão) --")
        print("1. Listar")
        print("2. Criar")
        print("3. Editar")
        print("4. Remover")
        print("5. Voltar")
        op = input("Escolha: ").strip()
        if op == "1":
            list_all_patients()
        elif op == "2":
            nome = input("Nome: ").strip()
            idade = validar_idade(input("Idade: ").strip()) or 0
            tel = input("Telefone: ").strip() or "Não informado"
            userlink = input("Vincular a username (opcional): ").strip() or None
            p = {"nome": nome, "idade": idade, "telefone": tel}
            if userlink: p["user"] = userlink
            patients.append(p); save_json(PATIENTS_FILE, patients); log(f"Gestão criou paciente {nome}")
        elif op == "3":
            list_all_patients()
            idx = input("Número do paciente para editar: ").strip()
            try:
                i = int(idx)-1; p = patients[i]
            except:
                print("Inválido"); continue
            p['nome'] = input(f"Nome [{p['nome']}]: ").strip() or p['nome']
            idade_txt = input(f"Idade [{p['idade']}]: ").strip()
            p['idade'] = validar_idade(idade_txt) if idade_txt else p['idade']
            p['telefone'] = input(f"Telefone [{p['telefone']}]: ").strip() or p['telefone']
            p['user'] = input(f"Username vinculado [{p.get('user','')}]: ").strip() or p.get('user')
            save_json(PATIENTS_FILE, patients); log(f"Gestão editou paciente {p['nome']}")
        elif op == "4":
            list_all_patients()
            idx = input("Número do paciente para remover: ").strip()
            try:
                i = int(idx)-1; p = patients.pop(i)
                save_json(PATIENTS_FILE, patients); log(f"Gestão removeu paciente {p['nome']}")
                print("Removido.")
            except:
                print("Inválido")
        elif op == "5":
            break
        else:
            print("Inválido.")

def admin_manage_invoices():
    while True:
        print("\n-- Gestão Faturas --")
        print("1. Listar")
        print("2. Criar")
        print("3. Editar parcela")
        print("4. Remover")
        print("5. Voltar")
        op = input("Escolha: ").strip()
        if op == "1":
            for inv in invoices:
                print(f"ID {inv['id']} - paciente {inv['patient_user']} - total {inv['total']}")
        elif op == "2":
            u = input("Username do paciente: ").strip()
            create_invoice(u)
        elif op == "3":
            admin_edit_invoice()
        elif op == "4":
            id_txt = input("ID da fatura a remover: ").strip()
            try:
                id_int = int(id_txt); inv = next(i for i in invoices if i['id']==id_int)
                invoices.remove(inv); save_json(INVOICES_FILE, invoices); log(f"Gestão removeu fatura {id_int}")
                print("Removido.")
            except:
                print("Inválido.")
        elif op == "5":
            break
        else:
            print("Inválido.")

def admin_manage_appointments():
    reload_all()
    if not appointments: print("Nenhum agendamento."); return
    for a in appointments:
        print(f"ID {a['id']} - Paciente: {a['patient_name']} user:{a.get('patient_user')} - Médico:{a.get('doctor_user')} - {a['datetime']} - {a['status']}")
    print("Para editar, use o hub médico ou remova/edit em gestão via edição direta se necessário.")

# -------------------------
# Export / relatório / simulação
# -------------------------
def export_csv(filename=CSV_FILE):
    reload_all()
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["nome","idade","telefone","user"], delimiter=';')
        writer.writeheader()
        for p in patients:
            writer.writerow({"nome": p.get("nome"), "idade": p.get("idade"), "telefone": p.get("telefone"), "user": p.get("user","")})
    log("CSV exportado")
    print("CSV exportado:", filename)

def gerar_relatorio_txt(path=REPORT_FILE):
    reload_all()
    if not patients:
        print("Sem pacientes.")
        return
    total = len(patients); media = sum(p['idade'] for p in patients)/total if total else 0
    with open(path, "w", encoding="utf-8") as f:
        f.write("Relatório Clínica Vida+\n")
        f.write("="*40+"\n")
        f.write(f"Total pacientes: {total}\nIdade média: {media:.2f}\n\n")
        f.write("Pacientes:\n")
        for p in patients:
            f.write(f"- {p.get('nome')} | {p.get('idade')} | {p.get('telefone')} | user: {p.get('user','')}\n")
    log("Relatório gerado")
    print("Relatório gerado:", path)

def simular_fila():
    fila = deque()
    for i in range(1,4):
        nome = input(f"Nome paciente {i}: ").strip()
        cpf = input(f"CPF paciente {i}: ").strip()
        fila.append({"nome":nome,"cpf":cpf})
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

# -------------------------
# HUB inicial e main loop
# -------------------------
def initial_hub():
    reload_all()
    print("\n=== CLÍNICA VIDA+ ===")
    print("Qual é a sua função?")
    print("1. Sou Paciente")
    print("2. Sou Médico")
    print("3. Sou da Gestão")
    print("4. Sair")
    opt = input("Escolha: ").strip()
    if opt == "1":
        print("1. Login  2. Criar conta (paciente)")
        o = input("Escolha: ").strip()
        if o == "1":
            user = autenticar("paciente")
            if user: hub_paciente(user)
        elif o == "2":
            criar_usuario("paciente")
        else:
            print("Inválido.")
    elif opt == "2":
        print("1. Login  2. Criar conta (médico)")
        o = input("Escolha: ").strip()
        if o == "1":
            user = autenticar("medico")
            if user: hub_medico(user)
        elif o == "2":
            medico_create_hub()
        else:
            print("Inválido.")
    elif opt == "3":
        user = autenticar("gestao")
        if user: hub_gestao(user)
    elif opt == "4":
        return False
    else:
        print("Inválido.")
    return True

def main():
    # cria usuário gestor padrão se não existir
    reload_all()
    if not any(u['role']=="gestao" for u in users):
        users.append({"username":"admin","password":"admin","role":"gestao","name":"Administrador"})
        save_json(USERS_FILE, users)
        log("Usuário gestor padrão criado (admin/admin).")
        print("Usuário gestor padrão criado -> admin / admin")
    continuar = True
    while continuar:
        continuar = initial_hub()
        input("Pressione Enter para continuar...")

if __name__ == "__main__":
    main()
