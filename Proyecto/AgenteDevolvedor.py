# -*- coding: utf-8 -*-
from imports import *

__author__ = 'adrian'

argumentos = getArguments(my_port=8003)
#Direcciones hardcodeadas (propia)
host = argumentos['host']
port = argumentos['port']

centroLogistico = argumentos['name']

directorio_host = argumentos['dir_host']
directorio_port = argumentos['dir_port']

ont = Namespace('Ontologias/root-ontology.owl')
agn = getAgentNamespace()

devolvedor = getNamespace('AgenteDevolvedor')
monetario = getNamespace('AgenteMonetario')
usuario = getNamespace('AgenteUsuario')
#Objetos agente
AgenteDevolvedor = Agent('AgenteDevolvedor',devolvedor['generic'],formatDir(host,port) + '/comm',None)
DirectorioAgentes = Agent('DirectorioAgentes',agn.Directory,formatDir(directorio_host,directorio_port) + '/comm',None)

devoluciones_ns = getNamespace('Devoluciones')
devoluciones_db = 'Datos/devoluciones.turtle'
devoluciones = Graph()

pedidos_ns = getNamespace('Pedidos')
pedidos_db = 'Datos/pedidos.turtle'
pedidos = Graph()

productos_ns = getNamespace('Productos')
productos_db = 'Datos/productos.turtle'
productos = Graph()

# Flask stuff
app = Flask(__name__,template_folder="AgenteDevolvedor/templates")

#Acciones. Este diccionario sera cargado con todos los procedimientos que hay que llamar dinamicamente 
# cuando llega un mensaje
actions = {}

#Carga los grafoos rdf de los distintos ficheros
def cargarGrafos():
    global devoluciones
    global pedidos
    global productos
    devoluciones = Graph()
    pedidos = Graph()
    productos = Graph()
    if os.path.isfile(devoluciones_db):
        devoluciones.parse(devoluciones_db,format="turtle")
    if os.path.isfile(pedidos_db):
        pedidos.parse(pedidos_db,format="turtle")
    if os.path.isfile(productos_db):
        productos.parse(productos_db,format="turtle")
    

def guardarGrafo(g,file):
    g.serialize(file,format="turtle")   

def nuevaDevolucion(graph):     #empieza un thread de decidirDevolucion
    """
    ab1 = Process(target=decidirDevolucion, args=(graph))
    ab1.start()
    """
    decidirDevolucion(graph)
    return create_confirm(AgenteDevolvedor,None)

def decidirDevolucion(graph):   #decidir si se acepta o no la devolucion (RazonDevolucion == ("Defectuoso" || "Equivocado" || "NoSatisface"))
    for s,p,o in graph.triples((ont.Devolucion, ont.RazonDevolucion, None)):
        if str(o) == "NoSatisface": #TODO si hace mas de 15 dias desde la recepcion rechazarlo, si no aceptarlo
            comprobar15Dias(graph)
        elif str(o) == "Defectuoso":
            print("entro aqui")
            elegirEmpresaMensajeria(graph, "Defectuoso")
        elif str(o) == "Equivocado":
            elegirEmpresaMensajeria(graph, "Equivocado")

def comprobar15Dias(graph):
    global ont
    global pedidos
    global pedidos_ns

    idPedido = None
    idProducto = None
    for s,p,o in graph.triples((ont.Devolucion,None,None)):
        if p == ont.Pedido:
            idPedido = str(o)
        if p == ont.Producto:
            idProducto = str(o)    
    fecha = None
    dict = pedido_a_dict(pedidos,pedidos_ns[idPedido])
    print(str(dict))
    for item in dict['productos']:
        if item['id'] == idProducto:
            fecha = item['fechaEntrega']

    year,month,day = fecha.split("-")
    year = int(year)
    month = int(month)
    day = int(day)

    now = datetime.datetime.now()
    yearToday = int(now.year)
    monthToday = int(now.month)
    dayToday = int(now.day)
    aceptado = True
    if yearToday == year:
        if monthToday == month:
            if (dayToday - day) > 15:
                aceptado = False
        elif (monthToday - 1) == month:
            daysTo30 = abs(day - 30)
            if (dayToday + daysTo30) > 15:
                aceptado = False
        else:
            aceptado = False
    else:
        aceptado = False

    if aceptado:
        elegirEmpresaMensajeria(graph, "NoSatisface")
    else:
        comunicarRespuesta(graph, False, None, None)

def elegirEmpresaMensajeria(graph, razon): #elegir la empresa de mensajeria
    rand = randint(0,3)
    mensajeria = None
    direccion = None
    if rand == 0:
        mensajeria = "Correos"
    elif rand == 1:
        mensajeria = "Seur"
    elif rand == 2:
        mensajeria = "UPS"
    elif rand == 3:
        mensajeria = "ASM"

    if razon == "NoSatisface":
        direccion = "Revision"
    elif razon == "Defectuoso":
        direccion = "Vertedero"
    elif razon == "Equivocado":
        direccion = "Tienda"

    comunicarRespuesta(graph, True, mensajeria, direccion, razon)

def comunicarRespuesta(graph, aceptado, mensajeria, direccion, razon): #si se ha aceptado o no enviar la respuesta al agente de usuario
    global productos
    global ont

    persona = None
    importe = None
    producto = None
    for p, o in graph[ont.Devolucion]:
        if p == ont.Usuario:
            persona = str(o)
        if p == ont.Producto:
            producto = str(o)

    # hay que mirar la base de datos de productos para ver el importe a devolver
    for s,p,o in productos.triples((productos_ns[producto], productos_ns.Importe, None)):
        importe = str(o)

    if aceptado:
        crearDevolucion(graph, mensajeria, direccion, razon, persona, importe, producto, aceptado)
    """
    #enviar la respuesta al agente de usuario
    obj = createAction(AgenteUsuario,'respuestaDevolucion')

    gcom = Graph()
    gcom.add((ont.Devolucion,ont.Producto,Literal(producto)))
    gcom.add((ont.Devolucion,ont.Razon,Literal(razon)))
    estado = None
    if aceptado:
        estado = "En marcha"
    else:
        estado = "Denegado"
    gcom.add((ont.Devolucion,ont.Estado,Literal(estado)))
    gcom.add((ont.Devolucion,RDF.type,devoluciones_ns.type))
    gcom.add((obj,RDF.type,agn.RespuestaDevolucion))

    msg = build_message(gcom,
        perf=ACL.request,
        sender=AgenteDevolvedor.uri,
        content=obj)

    # Enviamos el mensaje a cualquier agente monetario
    send_message_any(msg,AgenteDevolvedor,DirectorioAgentes,usuario.type)
    """
def crearDevolucion(graph, mensajeria, direccion, razon, persona, importe, producto, aceptado):
    global devoluciones_ns

    fecha = datetime.date.today()
    estado = None
    if aceptado:
        estado = "En marcha"
    else:
        estado = "Denegado"


    rand = randint(0, 50)
    devoluciones.add((devoluciones_ns[rand], devoluciones_ns.Persona, Literal(persona)))
    devoluciones.add((devoluciones_ns[rand], devoluciones_ns.Producto, Literal(producto)))
    devoluciones.add((devoluciones_ns[rand], devoluciones_ns.Importe, Literal(importe)))
    devoluciones.add((devoluciones_ns[rand], devoluciones_ns.Fecha, Literal(fecha)))
    devoluciones.add((devoluciones_ns[rand], devoluciones_ns.EmpresaMensajeria, Literal(mensajeria)))
    devoluciones.add((devoluciones_ns[rand], devoluciones_ns.Direccion, Literal(direccion)))
    devoluciones.add((devoluciones_ns[rand], devoluciones_ns.Razon, Literal(razon)))
    devoluciones.add((devoluciones_ns[rand], devoluciones_ns.Estado, Literal(estado)))
    guardarGrafo(devoluciones, devoluciones_db)

@app.route("/Devoluciones")
def getDevoluciones():
    global devoluciones
    global devoluciones_ns

    idUsuario = request.args['id']

    array = [[]]
    for s,p,o in devoluciones.triples((None, devoluciones_ns.Persona, idUsuario)):
        aux = []
        for ss,pp,oo in devoluciones.triples((s, None, None)):
            aux.append(str(oo))
        array.append(aux)

    return render_template('lista_devoluciones.html', a = array, u = idUsuario)

def pedirReembolso(persona, importe):      #pedir al agente monetario el reembolso del importe del producto
    global ont
    obj = createAction(AgenteMonetario,'pedirDevolucion')

    gcom = Graph()
    #ontologias
    gcom.add((ont.Pago,ont.Persona,Literal(persona)))
    gcom.add((ont.Pago,ont.Importe,Literal(importe)))
    gcom.add((obj,RDF.type,agn.MonetarioPedirDevolucion))

    msg = build_message(gcom,
        perf=ACL.request,
        sender=AgenteDevolvedor.uri,
        content=obj)

    # Enviamos el mensaje a cualquier agente monetario
    send_message_any(msg,AgenteDevolvedor,DirectorioAgentes,monetario.type)

def finalizarDevolucion(graph):
    global devoluciones
    global devoluciones_db
    global devoluciones_ns
    global ont

    idDev = None
    for s,p,o in graph.triples((ont.Devolucion, ont.IdDevolucion, None)):
        idDev = int(o)

    devoluciones.set((devoluciones_ns[idDev], devoluciones_ns.Estado, Literal("Finalizado")))
    guardarGrafo(devoluciones, devoluciones_db)


    persona = importe = None
    for s,p,o in graph.triples((devoluciones_ns[idDev])):
        if p == devoluciones_ns.Persona:
            persona = str(o)
        if p == devoluciones_ns.Importe:
            importe = int(o)

    pedirReembolso(persona, importe)

@app.route("/comm")
def comunicacion():
    global actions
    global AgenteDevolvedor
    # Extraemos el mensaje y creamos un grafo con él
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)
    # Comprobamos que sea un mensaje FIPA ACL y que la performativa sea correcta
    if not msgdic or msgdic['performative'] != ACL.request:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = create_notUnderstood(AgenteDevolvedor,None)
    else:
        content = msgdic['content']
        # Averiguamos el tipo de la accion
        accion = gm.value(subject=content, predicate=RDF.type)

        #Llamada dinamica a la accion correspondiente
        if accion in actions:
            gr = actions[accion](gm)
        else:
            gr = create_notUnderstood(AgenteDevolvedor,None)

    return gr.serialize(format='xml')



@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    """
    Acciones previas a parar el agente

    """
    pass


def agentbehavior1(cola):
    """
    Un comportamiento del agente

    :return:
    """
    pass

def init_agent():
    register_message(AgenteDevolvedor,DirectorioAgentes,devolvedor.type)

def registerActions():
    global actions
    actions[agn.DevolvedorPedirDevolucion] = nuevaDevolucion
    actions[agn.DevolvedorDevolucionRecibida] = finalizarDevolucion

@app.route("/test1")
def test1():
    # test que hace una devolucion del usuario "adrian" del producto "productoprueba1"
    # del pedido "pedidoprueba1" por el motivo "Defectuoso"
    global ont
    obj = createAction(AgenteDevolvedor,'nuevaDevolucion')
    gcom = Graph()
    gcom.add((obj,RDF.type,agn.DevolvedorPedirDevolucion))
    
    gcom.add((ont.Devolucion, ont.Pedido, Literal("pedidoprueba1")))    #el objeto debera ser el identificador del pedido
    gcom.add((ont.Devolucion, ont.Producto, Literal("productoprueba1")))    #el objeto debera ser el identificador del producto en un pedido
    gcom.add((ont.Devolucion, ont.Usuario, Literal("adrian")))
    gcom.add((ont.Devolucion, ont.RazonDevolucion, Literal("Defectuoso")))

    msg = build_message(gcom,
        perf=ACL.request,
        sender=AgenteDevolvedor.uri,
        content=obj)
    send_message_any(msg,AgenteDevolvedor,DirectorioAgentes,devolvedor.type)

    return 'Exit'

@app.route("/test2")
def test2():
    # test que hace una devolucion del usuario "alex" del producto "productoprueba2"
    # del pedido "pedidoprueba2" por el motivo "NoSatisface"
    global ont
    obj = createAction(AgenteDevolvedor,'nuevaDevolucion')
    gcom = Graph()
    gcom.add((obj,RDF.type,agn.DevolvedorPedirDevolucion))
    
    gcom.add((ont.Devolucion, ont.Pedido, Literal("pedidoprueba2")))    #el objeto debera ser el identificador del pedido
    gcom.add((ont.Devolucion, ont.Producto, Literal("productoprueba2")))    #el objeto debera ser el identificador del producto en un pedido
    gcom.add((ont.Devolucion, ont.Usuario, Literal("alex")))
    gcom.add((ont.Devolucion, ont.RazonDevolucion, Literal("NoSatisface")))

    msg = build_message(gcom,
        perf=ACL.request,
        sender=AgenteDevolvedor.uri,
        content=obj)
    send_message_any(msg,AgenteDevolvedor,DirectorioAgentes,devolvedor.type)

    return 'Exit'

if __name__ == "__main__":
    # Ponemos en marcha los behaviors
    

    registerActions()

    cargarGrafos()
    init_agent()
    # Ponemos en marcha el servidor
    app.run(host=host, port=port, debug=True)

    print('The End')