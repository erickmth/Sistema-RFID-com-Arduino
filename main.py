import serial
import tkinter as tk
from tkinter import ttk, messagebox
import time
import csv
from datetime import datetime
import math
import threading
from PIL import Image, ImageTk
import os
import json

# ---------------- CONFIGURAÇÕES ----------------
PORTA_SERIAL = 'COM3'  # Substitua pela porta correta do Arduino
BAUD_RATE = 9600

# IDs cadastrados
operadores = {
    "056B4A806403E9": "Operador Suporte",
    "AD88C801": "Raquel",
}

# IDs de administradores
administradores = {
    "3A163602": "Admin Erick",
}

# Mapeamento de áreas para peças
areas_pecas = {
    "A1": "Eixos",
    "A2": "Chassi",
    "A3": "Lanternas",
    "A4": "Parabrisas",
    "A5": "Rodas",
    "A6": "Teto"
}

# Estoque inicial (será carregado/salvo durante a execução)
estoque = {
    "A1": {"peca": "Eixos", "quantidade": 100, "minimo": 20},
    "A2": {"peca": "Chassi", "quantidade": 50, "minimo": 10},
    "A3": {"peca": "Lanternas", "quantidade": 200, "minimo": 30},
    "A4": {"peca": "Parabrisas", "quantidade": 30, "minimo": 5},
    "A5": {"peca": "Rodas", "quantidade": 80, "minimo": 15},
    "A6": {"peca": "Teto", "quantidade": 25, "minimo": 5}
}

# ---------------- VARIÁVEIS GLOBAIS ----------------
area_var = None
peca_var = None
quantidade_entry = None
form_frame = None
ultimo_rfid_lido = None
ultimo_tempo_leitura = 0
bloquear_leitura = False
wave_offset = 0  # Para animação
ser = None
serial_thread = None
running = True
last_activity_time = time.time()
wave_animation_active = False
logout_timer = None
status_label = None
wave_canvas = None
estoque_frame = None
current_user = None  # Nova variável para controlar usuário atual

# Dicionário para manter referências das imagens (evita garbage collection)
IMAGES = {}

# ---------------- FUNÇÕES DE ESTOQUE ----------------

def carregar_estoque():
    """Carrega o estoque de um arquivo temporário se existir"""
    global estoque
    try:
        if os.path.exists('estoque_temp.json'):
            with open('estoque_temp.json', 'r') as f:
                estoque = json.load(f)
            print("Estoque carregado do arquivo temporário")
    except Exception as e:
        print(f"Erro ao carregar estoque: {e}")

def salvar_estoque():
    """Salva o estoque em um arquivo temporário"""
    try:
        with open('estoque_temp.json', 'w') as f:
            json.dump(estoque, f)
        print("Estoque salvo no arquivo temporário")
    except Exception as e:
        print(f"Erro ao salvar estoque: {e}")

def atualizar_estoque(area, quantidade):
    """Atualiza o estoque após uma reposição (SUBTRAI)"""
    if area in estoque:
        estoque[area]["quantidade"] -= quantidade
        salvar_estoque()
        return True
    return False

def verificar_estoque_minimo():
    """Verifica se algum item está abaixo do estoque mínimo"""
    alertas = []
    for area, dados in estoque.items():
        if dados["quantidade"] <= dados["minimo"]:
            alertas.append(f"{area} ({dados['peca']}): {dados['quantidade']} unidades (mínimo: {dados['minimo']})")
    return alertas

# ---------------- FUNÇÕES PRINCIPAIS ----------------

def reset_inactivity_timer():
    """Reinicia o timer de inatividade"""
    global last_activity_time, logout_timer
    last_activity_time = time.time()
    
    # Cancela o timer anterior se existir
    if logout_timer:
        root.after_cancel(logout_timer)
    
    # Agenda novo logout para 60 segundos (apenas se estiver logado)
    if current_user:
        logout_timer = root.after(60000, logout_by_inactivity)

def logout_by_inactivity():
    """Desloga por inatividade"""
    global bloquear_leitura, current_user
    if not current_user:
        return  # Já está na tela inicial
    
    messagebox.showinfo("Sessão Expirada", "Sessão encerrada por inatividade.")
    current_user = None
    voltar_tela_inicial()

def salvar_reposicao(nome, area, peca, quantidade):
    """Salva os dados em CSV"""
    with open('reposicoes.csv', 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), nome, area, peca, quantidade])
    
    # Atualiza o estoque (SUBTRAI)
    if atualizar_estoque(area, quantidade):
        print(f"Estoque atualizado: {area} -{quantidade}")

def mostrar_formulario(nome):
    """Exibe o formulário de reposição"""
    global area_var, peca_var, quantidade_entry, bloquear_leitura, wave_animation_active, current_user
    bloquear_leitura = True  # Agora bloqueia a leitura de RFID
    wave_animation_active = False
    current_user = nome
    
    for widget in root.winfo_children():
        widget.destroy()
    
    # Frame principal com gradiente
    main_frame = tk.Frame(root, bg='white')
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Título
    title_frame = tk.Frame(main_frame, bg='white')
    title_frame.pack(fill=tk.X, pady=(0, 30))
    
    # Ícone do formulário
    icon_form = load_icon("form_icon.png", 40)
    if icon_form:
        label_form_icon = tk.Label(title_frame, image=icon_form, bg='white')
        label_form_icon.image = icon_form
        label_form_icon.pack()
    
    tk.Label(title_frame, text=f"Registro de Reposição", 
             font=("Segoe UI", 24, "bold"), bg='white', fg='#2c3e50').pack(pady=(10, 5))
    tk.Label(title_frame, text=f"Operador: {nome}", 
             font=("Segoe UI", 16), bg='white', fg='#7f8c8d').pack()
    
    # Exibir alertas de estoque mínimo
    alertas = verificar_estoque_minimo()
    if alertas:
        alert_frame = tk.Frame(main_frame, bg='#fff3cd', relief=tk.RAISED, bd=1)
        alert_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(alert_frame, text="⚠️ ALERTA: Estoque mínimo atingido:", 
                font=("Segoe UI", 12, "bold"), bg='#fff3cd', fg='#856404').pack(anchor=tk.W, padx=10, pady=5)
        for alerta in alertas:
            tk.Label(alert_frame, text=f"• {alerta}", 
                    font=("Segoe UI", 10), bg='#fff3cd', fg='#856404').pack(anchor=tk.W, padx=20, pady=2)
    
    # Formulário
    form_frame = tk.Frame(main_frame, bg='white')
    form_frame.pack(fill=tk.BOTH, expand=True)
    
    # Área
    area_frame = tk.Frame(form_frame, bg='white')
    area_frame.pack(fill=tk.X, pady=15)
    tk.Label(area_frame, text="Área de reposição:", font=("Segoe UI", 14), 
             bg='white', fg='#2c3e50').pack(anchor=tk.W)
    area_var = tk.StringVar()
    
    # Combobox com altura aumentada para mostrar todos os itens
    area_cb = ttk.Combobox(area_frame, textvariable=area_var, 
                           values=list(areas_pecas.keys()), 
                           state="readonly", font=("Segoe UI", 14), 
                           height=10)
    area_cb.pack(fill=tk.X, pady=(10, 0))
    area_cb.bind('<<ComboboxSelected>>', atualizar_peca)
    area_cb.bind('<FocusIn>', lambda e: reset_inactivity_timer())
    area_cb.bind('<Key>', lambda e: reset_inactivity_timer())
    area_cb.bind('<Button-1>', lambda e: reset_inactivity_timer())
    
    # Peça e Estoque Atual
    peca_frame = tk.Frame(form_frame, bg='white')
    peca_frame.pack(fill=tk.X, pady=15)
    tk.Label(peca_frame, text="Peça a repor:", font=("Segoe UI", 14), 
             bg='white', fg='#2c3e50').pack(anchor=tk.W)
    
    peca_info_frame = tk.Frame(peca_frame, bg='white')
    peca_info_frame.pack(fill=tk.X, pady=(10, 0))
    
    peca_var = tk.StringVar(value="Selecione uma área")
    tk.Label(peca_info_frame, textvariable=peca_var, font=("Segoe UI", 14, "bold"), 
             foreground="#3498db", bg='white').pack(side=tk.LEFT)
    
    # Label para mostrar estoque atual e mínimo
    estoque_label = tk.Label(peca_info_frame, text="", font=("Segoe UI", 12), 
                            foreground="#7f8c8d", bg='white')
    estoque_label.pack(side=tk.RIGHT)
    
    def atualizar_estoque_display(event=None):
        area = area_var.get()
        if area in estoque:
            estoque_atual = estoque[area]["quantidade"]
            minimo = estoque[area]["minimo"]
            cor = "#e74c3c" if estoque_atual <= minimo else "#27ae60"
            estoque_label.config(
                text=f"Estoque: {estoque_atual} | Mínimo: {minimo}",
                fg=cor
            )
        else:
            estoque_label.config(text="")
    
    area_var.trace('w', lambda *args: atualizar_estoque_display())
    
    # Quantidade com informação do mínimo necessário
    quantidade_frame = tk.Frame(form_frame, bg='white')
    quantidade_frame.pack(fill=tk.X, pady=15)
    
    quantidade_header_frame = tk.Frame(quantidade_frame, bg='white')
    quantidade_header_frame.pack(fill=tk.X)
    
    tk.Label(quantidade_header_frame, text="Quantidade:", font=("Segoe UI", 14), 
             bg='white', fg='#2c3e50').pack(side=tk.LEFT)
    
    # Label para mostrar o mínimo necessário DESTACADO
    minimo_label = tk.Label(quantidade_header_frame, text="", font=("Segoe UI", 12, "bold"), 
                           foreground="#e67e22", bg='white')
    minimo_label.pack(side=tk.RIGHT)
    
    def atualizar_minimo_display(event=None):
        area = area_var.get()
        if area in estoque:
            minimo = estoque[area]["minimo"]
            minimo_label.config(text=f"Quantidade Mínima no Processo: {minimo} peças")
        else:
            minimo_label.config(text="")
    
    area_var.trace('w', lambda *args: atualizar_minimo_display())
    
    quantidade_entry = ttk.Spinbox(quantidade_frame, from_=1, to=1000, 
                                  font=("Segoe UI", 14), width=10)
    quantidade_entry.pack(anchor=tk.W, pady=(10, 0))
    quantidade_entry.delete(0, tk.END)
    quantidade_entry.insert(0, "1")
    quantidade_entry.bind('<FocusIn>', lambda e: reset_inactivity_timer())
    quantidade_entry.bind('<Key>', lambda e: reset_inactivity_timer())
    
    # Botões
    button_frame = tk.Frame(form_frame, bg='white')
    button_frame.pack(fill=tk.X, pady=(40, 0))
    
    btn_style = ttk.Style()
    btn_style.configure('Success.TButton', font=('Segoe UI', 12), background='#2ecc71', foreground='white')
    btn_style.configure('Danger.TButton', font=('Segoe UI', 12), background='#e74c3c', foreground='white')
    
    # Ícone de registro
    icon_register = load_icon("register_icon.png", 20)
    icon_cancel = load_icon("cancel_icon.png", 20)
    
    register_btn = ttk.Button(button_frame, text="Registrar", style='Success.TButton',
               command=lambda: registrar_reposicao(nome))
    register_btn.pack(side=tk.RIGHT, padx=(10, 0))
    if icon_register:
        register_btn.image = icon_register
        register_btn.configure(image=icon_register, compound=tk.LEFT)
    register_btn.bind('<Button-1>', lambda e: reset_inactivity_timer())
    
    cancel_btn = ttk.Button(button_frame, text="Cancelar", style='Danger.TButton',
               command=voltar_tela_inicial)
    cancel_btn.pack(side=tk.RIGHT)
    if icon_cancel:
        cancel_btn.image = icon_cancel
        cancel_btn.configure(image=icon_cancel, compound=tk.LEFT)
    cancel_btn.bind('<Button-1>', lambda e: reset_inactivity_timer())
    
    area_cb.focus()
    reset_inactivity_timer()

def atualizar_peca(event=None):
    """Atualiza a peça de acordo com a área"""
    area = area_var.get()
    if area in areas_pecas:
        peca_var.set(areas_pecas[area])
    reset_inactivity_timer()

def registrar_reposicao(nome):
    """Registra reposição"""
    area = area_var.get()
    peca = peca_var.get()
    try:
        quantidade = int(quantidade_entry.get())
        if quantidade <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Erro", "Quantidade inválida!")
        return
    if not area or peca == "Selecione uma área":
        messagebox.showerror("Erro", "Selecione uma área!")
        return
    
    # Verifica se há estoque suficiente
    if area in estoque and estoque[area]["quantidade"] < quantidade:
        messagebox.showerror("Erro", f"Estoque insuficiente! Disponível: {estoque[area]['quantidade']}")
        return
    
    salvar_reposicao(nome, area, peca, quantidade)
    messagebox.showinfo("Sucesso", f"Reposição registrada com sucesso!\n{quantidade} {peca} removidos do estoque.")
    voltar_tela_inicial()

def mostrar_painel_administrativo(nome):
    """Exibe o painel administrativo"""
    global bloquear_leitura, wave_animation_active, estoque_frame, current_user
    bloquear_leitura = True
    wave_animation_active = False
    current_user = nome
    
    for widget in root.winfo_children():
        widget.destroy()
    
    # Frame principal
    main_frame = tk.Frame(root, bg='white')
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Cabeçalho
    header_frame = tk.Frame(main_frame, bg='white')
    header_frame.pack(fill=tk.X, pady=(0, 20))
    
    icon_admin = load_icon("admin_icon.png", 40)
    if icon_admin:
        label_admin_icon = tk.Label(header_frame, image=icon_admin, bg='white')
        label_admin_icon.image = icon_admin
        label_admin_icon.pack()
    
    tk.Label(header_frame, text="Painel Administrativo", 
             font=("Segoe UI", 24, "bold"), bg='white', fg='#2c3e50').pack(pady=(10, 5))
    tk.Label(header_frame, text=f"Administrador: {nome}", 
             font=("Segoe UI", 16), bg='white', fg='#7f8c8d').pack()
    
    # Abas
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=10)
    
    # Aba de Estoque
    estoque_frame = tk.Frame(notebook, bg='white')
    notebook.add(estoque_frame, text="Gerenciar Estoque")
    
    # Tabela de estoque
    columns = ("Área", "Peça", "Quantidade", "Mínimo", "Status")
    tree = ttk.Treeview(estoque_frame, columns=columns, show="headings", height=8)
    
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=100, anchor=tk.CENTER)
    
    tree.column("Peça", width=120)
    tree.column("Status", width=120)
    
    # Scrollbar para a tabela
    scrollbar_table = ttk.Scrollbar(estoque_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar_table.set)
    
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    scrollbar_table.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Atualizar tabela
    atualizar_tabela_estoque(tree)
    
    # Frame para adicionar/editar item - AGORA COM LAYOUT MELHOR
    novo_item_frame = tk.Frame(estoque_frame, bg='white')
    novo_item_frame.pack(fill=tk.X, pady=10)
    
    tk.Label(novo_item_frame, text="Definir Estoque Mínimo:", 
             font=("Segoe UI", 12, "bold"), bg='white').pack(anchor=tk.W, pady=(10, 5))
    
    # Usar grid com mais linhas para melhor organização
    form_frame = tk.Frame(novo_item_frame, bg='white')
    form_frame.pack(fill=tk.X, pady=5)
    
    # Linha 1: Área e Peça
    tk.Label(form_frame, text="Área:", bg='white', font=("Segoe UI", 10)).grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
    area_entry = ttk.Combobox(form_frame, values=list(areas_pecas.keys()), width=8, state="readonly", font=("Segoe UI", 10))
    area_entry.grid(row=0, column=1, padx=5, pady=2)
    
    tk.Label(form_frame, text="Peça:", bg='white', font=("Segoe UI", 10)).grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)
    peca_var_admin = tk.StringVar()
    peca_label = tk.Label(form_frame, textvariable=peca_var_admin, bg='white', width=15, anchor=tk.W, font=("Segoe UI", 10))
    peca_label.grid(row=0, column=3, padx=5, pady=2, sticky=tk.W)
    
    # Linha 2: Quantidade e Mínimo
    tk.Label(form_frame, text="Quantidade Atual:", bg='white', font=("Segoe UI", 10)).grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
    quant_entry = ttk.Spinbox(form_frame, from_=0, to=10000, width=8, font=("Segoe UI", 10))
    quant_entry.grid(row=1, column=1, padx=5, pady=2)
    
    tk.Label(form_frame, text="Mínimo Necessário:", bg='white', font=("Segoe UI", 10)).grid(row=1, column=2, padx=5, pady=2, sticky=tk.W)
    min_entry = ttk.Spinbox(form_frame, from_=0, to=1000, width=8, font=("Segoe UI", 10))
    min_entry.grid(row=1, column=3, padx=5, pady=2)
    
    # Linha 3: Botão Salvar
    save_button = ttk.Button(form_frame, text="Salvar Configuração", 
              command=lambda: salvar_configuracao_admin(area_entry, quant_entry, min_entry, tree),
              width=20)
    save_button.grid(row=2, column=0, columnspan=4, pady=10)
    
    def atualizar_peca_admin(event=None):
        area = area_entry.get()
        if area in areas_pecas:
            peca_var_admin.set(areas_pecas[area])
    
    area_entry.bind('<<ComboboxSelected>>', atualizar_peca_admin)
    
    def carregar_dados_area():
        area = area_entry.get()
        if area in estoque:
            quant_entry.delete(0, tk.END)
            quant_entry.insert(0, str(estoque[area]["quantidade"]))
            min_entry.delete(0, tk.END)
            min_entry.insert(0, str(estoque[area]["minimo"]))
    
    area_entry.bind('<<ComboboxSelected>>', lambda e: carregar_dados_area())
    
    # Botão Voltar
    button_frame = tk.Frame(main_frame, bg='white')
    button_frame.pack(fill=tk.X, pady=10)
    
    back_button = ttk.Button(button_frame, text="Voltar", 
              command=voltar_tela_inicial)
    back_button.pack(side=tk.RIGHT)
    
    # Configurar eventos para reset do timer
    widgets = [area_entry, quant_entry, min_entry, save_button, back_button]
    for widget in widgets:
        widget.bind('<FocusIn>', lambda e: reset_inactivity_timer())
        widget.bind('<Button-1>', lambda e: reset_inactivity_timer())
    
    reset_inactivity_timer()

def salvar_configuracao_admin(area_entry, quant_entry, min_entry, tree):
    """Salva a configuração do estoque no painel administrativo"""
    area = area_entry.get()
    try:
        quantidade = int(quant_entry.get())
        minimo = int(min_entry.get())
    except ValueError:
        messagebox.showerror("Erro", "Valores inválidos!")
        return
    
    if not area:
        messagebox.showerror("Erro", "Selecione uma área!")
        return
    
    estoque[area] = {
        "peca": areas_pecas[area],
        "quantidade": quantidade,
        "minimo": minimo
    }
    salvar_estoque()
    atualizar_tabela_estoque(tree)
    messagebox.showinfo("Sucesso", "Configuração salva com sucesso!")
    reset_inactivity_timer()

def atualizar_tabela_estoque(tree):
    """Atualiza a tabela de estoque"""
    for item in tree.get_children():
        tree.delete(item)
    
    for area, dados in sorted(estoque.items()):
        status = "✅ Suficiente" if dados["quantidade"] > dados["minimo"] else "⚠️ Abaixo do mínimo"
        cor = "" if dados["quantidade"] > dados["minimo"] else "red"
        
        item = tree.insert("", tk.END, values=(
            area, 
            dados["peca"], 
            dados["quantidade"], 
            dados["minimo"],
            status
        ))
        
        if dados["quantidade"] <= dados["minimo"]:
            tree.set(item, "Status", "⚠️ Abaixo do mínimo")

def voltar_tela_inicial():
    """Retorna à tela inicial"""
    global bloquear_leitura, wave_animation_active, current_user
    bloquear_leitura = False  # Libera a leitura de RFID novamente
    wave_animation_active = True
    current_user = None
    
    for widget in root.winfo_children():
        widget.destroy()
    
    setup_main_screen()
    reset_inactivity_timer()

def draw_wave_animation():
    """Desenha a animação de onda"""
    global wave_offset, wave_animation_active
    
    if not wave_animation_active:
        if wave_canvas:
            wave_canvas.delete("all")
            width, height = 400, 100
            
            for i in range(width):
                r = int(236 - (236 - 52) * i / width)
                g = int(240 - (240 - 152) * i / width)
                b = int(241 - (241 - 219) * i / width)
                color = f'#{r:02x}{g:02x}{b:02x}'
                wave_canvas.create_line(i, 0, i, height, fill=color)
            
            wave_canvas.create_line(0, height/2, width, height/2, fill="#3498db", width=3)
            wave_canvas.create_line(0, height/2 + 15, width, height/2 + 15, fill="#2980b9", width=2)
            wave_canvas.create_line(0, height/2 - 15, width, height/2 - 15, fill="#2980b9", width=2)
        
        if running:
            root.after(100, draw_wave_animation)
        return
    
    if wave_canvas:
        wave_canvas.delete("all")
        width, height = 400, 100
        
        for i in range(width):
            r = int(236 - (236 - 52) * i / width)
            g = int(240 - (240 - 152) * i / width)
            b = int(241 - (241 - 219) * i / width)
            color = f'#{r:02x}{g:02x}{b:02x}'
            wave_canvas.create_line(i, 0, i, height, fill=color)
        
        points1 = []
        points2 = []
        points3 = []
        for x in range(0, width, 5):
            y1 = height/2 + 15 * math.sin((x + wave_offset) * 0.05)
            y2 = height/2 + 10 * math.cos((x + wave_offset) * 0.08 + 0.5) + 8
            y3 = height/2 + 8 * math.sin((x + wave_offset) * 0.07 + 1.0) - 8
            points1.append(x)
            points1.append(y1)
            points2.append(x)
            points2.append(y2)
            points3.append(x)
            points3.append(y3)
        
        if len(points1) > 2:
            wave_canvas.create_line(points1, fill="#3498db", smooth=True, width=3)
            wave_canvas.create_line(points2, fill="#2980b9", smooth=True, width=2)
            wave_canvas.create_line(points3, fill="#1abc9c", smooth=True, width=2)
        
        wave_offset += 2
        if wave_animation_active and running:
            root.after(30, draw_wave_animation)

def start_wave_animation():
    """Inicia a animação das ondas"""
    global wave_animation_active
    wave_animation_active = True
    draw_wave_animation()
    root.after(3000, stop_wave_animation)

def stop_wave_animation():
    """Para a animação das ondas"""
    global wave_animation_active
    wave_animation_active = False

def processar_rfid(rfid_tag):
    """Processa o RFID lido"""
    global ultimo_rfid_lido, ultimo_tempo_leitura, bloquear_leitura
    
    if bloquear_leitura:
        print("Leitura bloqueada - formulário aberto")
        return
    
    tempo_atual = time.time()
    if rfid_tag == ultimo_rfid_lido and (tempo_atual - ultimo_tempo_leitura) < 3:
        print("Leitura duplicada ignorada")
        return
    ultimo_rfid_lido = rfid_tag
    ultimo_tempo_leitura = tempo_atual
    
    # Primeiro mostra que o cartão foi lido
    status_label.config(text="Cartão detectado...", fg="#f39c12")
    root.update()
    
    # Delay de 1 segundo antes de mostrar o nome
    root.after(1000, lambda: processar_rfid_com_delay(rfid_tag))

def processar_rfid_com_delay(rfid_tag):
    """Processa o RFID após o delay"""
    # Verifica se é administrador
    if rfid_tag.strip() in administradores:
        nome = administradores[rfid_tag.strip()]
        status_label.config(text=f"Administrador detectado! Olá, {nome}", fg="#9b59b6")
        start_wave_animation()
        root.update()
        root.after(800, lambda: mostrar_painel_administrativo(nome))
        return
    
    # Verifica se é operador normal
    nome = operadores.get(rfid_tag.strip(), None)
    
    if nome:
        status_label.config(text=f"Cartão reconhecido! Olá, {nome}", fg="#27ae60")
        start_wave_animation()
        root.update()
        root.after(800, lambda: mostrar_formulario(nome))
    else:
        status_label.config(text="ID não reconhecido!", fg="#e74c3c")
        root.update()
        root.after(1200, lambda: status_label.config(text="Aproxime o cartão do leitor...", fg="#3498db"))
    
    reset_inactivity_timer()

def ler_serial_continuamente():
    """Lê continuamente da porta serial em uma thread separada"""
    global ser, running, bloquear_leitura
    while running:
        if ser and ser.in_waiting > 0:
            try:
                rfid_data = ser.readline()
                rfid_tag = rfid_data.decode('utf-8').strip()
                if rfid_tag:
                    print(f"RFID lido: {rfid_tag}")
                    root.after(0, lambda: processar_rfid(rfid_tag))
            except (UnicodeDecodeError, serial.SerialException) as e:
                print(f"Erro na serial: {e}")
        time.sleep(0.1)

def load_icon(filename, size):
    """Carrega um ícone do disco usando caminho absoluto e guarda referência"""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, filename)
        if not os.path.exists(path):
            # não encontrado
            print(f"[load_icon] não encontrou: {path}")
            return None
        # abrir e redimensionar mantendo proporção simples
        img = Image.open(path)
        img = img.resize((size, size), Image.LANCZOS)
        tkimg = ImageTk.PhotoImage(img)
        # guarda referência no dicionário global para evitar GC
        IMAGES[f"{filename}_{size}"] = tkimg
        return tkimg
    except Exception as e:
        print(f"[load_icon] erro ao abrir {filename}: {e}")
        return None

def setup_main_screen():
    """Configura a tela inicial"""
    global status_label, wave_canvas
    
    # Frame principal
    main_frame = tk.Frame(root, bg='white')
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Título
    title_frame = tk.Frame(main_frame, bg='white')
    title_frame.pack(pady=(40, 10))
    
    # Ícone do sistema
    icon_system = load_icon("system_icon.png", 60)
    if icon_system:
        label_icon = tk.Label(title_frame, image=icon_system, bg='white')
        label_icon.image = icon_system
        label_icon.pack()
    
    tk.Label(title_frame, text="MDC System", 
             font=("Segoe UI", 28, "bold"), bg='white', fg='#2c3e50').pack(pady=(10, 5))
    tk.Label(title_frame, text="Replenishment System", 
             font=("Segoe UI", 18), bg='white', fg='#7f8c8d').pack(pady=(0, 40))
    
    # Status
    status_label = tk.Label(main_frame, text="Aproxime o cartão do leitor...", 
                           font=("Segoe UI", 18), fg="#3498db", bg='white')
    status_label.pack(pady=(0, 20))
    
    # Animação de onda
    wave_canvas = tk.Canvas(main_frame, width=400, height=100, 
                           highlightthickness=0, bg='white')
    wave_canvas.pack(pady=20)
    
    # Botão de sair
    footer_frame = tk.Frame(main_frame, bg='white')
    footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)
    
    # Ícone de saída
    icon_exit = load_icon("exit_icon.png", 20)
    
    exit_btn = ttk.Button(footer_frame, text="Sair", command=on_closing)
    exit_btn.pack()
    if icon_exit:
        exit_btn.image = icon_exit
        exit_btn.configure(image=icon_exit, compound=tk.LEFT)
    
    draw_wave_animation()

def on_closing():
    """Função chamada ao fechar a aplicação"""
    global running, ser, logout_timer
    running = False
    
    if logout_timer:
        root.after_cancel(logout_timer)
    
    if ser:
        try:
            ser.close()
        except:
            pass
    root.destroy()

# ---------------- INICIALIZAÇÃO ----------------
root = tk.Tk()
root.title("MDC System - Replenishment System")
root.geometry("1000x800")
root.configure(bg='white')
root.eval('tk::PlaceWindow . center')
root.protocol("WM_DELETE_WINDOW", on_closing)

# Configurar estilo
style = ttk.Style()
style.theme_use('clam')
style.configure('TButton', font=('Segoe UI', 12))
style.configure('TCombobox', font=('Segoe UI', 12))
style.configure('TSpinbox', font=('Segoe UI', 12))

# Carregar estoque
carregar_estoque()

# Configurar a interface inicial
setup_main_screen()

# ---------------- SERIAL ----------------
try:
    ser = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
    print(f"Conectado à porta {PORTA_SERIAL}")
    
    serial_thread = threading.Thread(target=ler_serial_continuamente, daemon=True)
    serial_thread.start()
except serial.SerialException:
    messagebox.showwarning("Aviso", f"Não foi possível conectar à porta {PORTA_SERIAL}\nModo simulação ativado.")
    ser = None
    
    def simular_leitura(event):
        if not bloquear_leitura:
            if event.x > root.winfo_width() // 2:
                processar_rfid("3A163602")  # Admin (clique direito)
            else:
                processar_rfid("AD88C801")  # Operador (clique esquerdo)
    
    root.bind('<Button-1>', simular_leitura)
    # se status_label ainda não foi definido por qualquer motivo, garante texto seguro:
    try:
        status_label.config(text="Modo simulação - Clique: esq=Operador, dir=Admin")
    except:
        pass

# Inicia o timer de inatividade
reset_inactivity_timer()

root.mainloop()