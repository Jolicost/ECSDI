from __future__ import print_function
from multiprocessing import Process
import os.path
#Clase agente
from Util.Agente import Agent
#Renders del flask
from flask import Flask, request, render_template,redirect
from time import sleep
#Funciones para recuperar las direcciones de los agentes
from Util.GestorDirecciones import formatDir
from Util.ACLMessages import build_message, get_message_properties, send_message
from Util.OntoNamespaces import ACL, DSO
from Util.Directorio import *
from Util.ModelParser import *
from Util.GraphUtil import *
#Diccionario con los espacios de nombres de la tienda
from Util.Namespaces import getNamespace,getAgentNamespace,createAction
#Utilidades de RDF
from rdflib import Graph, Namespace, Literal,BNode
from rdflib.namespace import FOAF, RDF

app = Flask(__name__,template_folder="AgenteTransportista/templates")

#Direcciones hardcodeadas (propia)
host = 'localhost'
port = 6000
nombre = 'transportista'

directorio_host = 'localhost'
directorio_port = 9000

enviador = getNamespace('AgenteEnviador')
productos = getNamespace('Productos')
transportista_ns = getNamespace('AgenteTransportista')
lotes_ns = getNamespace('Lotes')
envios_ns = getNamespace('Envios')

agn = getAgentNamespace()

g = Graph()

#Objetos agente, no son necesarios en toda regla pero sirven para agilizar comunicaciones
AgenteTransportista = Agent('AgenteTransportista',transportista[nombre],formatDir(host,port) + '/comm',None)
DirectorioAgentes = Agent('DirectorioAgentes',agn.Directory,formatDir(directorio_host,directorio_port) + '/comm',None)
#Cargar el grafo de datos
graphFile = 'AgenteTransportista/' + nombre + '.turtle'

#Acciones. Este diccionario sera cargado con todos los procedimientos que hay que llamar dinamicamente
# cuando llega un mensaje
actions = {}

#Carga el grafo rdf del fichero graphFile
def cargarGrafo():
	global g
	if os.path.isfile(graphFile):
		g.parse(graphFile,format="turtle")
	return g

#cargamos el grafo
g = cargarGrafo()

@app.route("/comm")
def comunicacion():
	# Extraemos el mensaje y creamos un grafo con el
	message = request.args['content']
	gm = Graph()
	gm.parse(data=message)

	msgdic = get_message_properties(gm)
	gr = None
	# Comprobamos que sea un mensaje FIPA ACL y que la performativa sea correcta
	if not msgdic:
		# Si no es, respondemos que no hemos entendido el mensaje
		gr = create_notUnderstood(AgenteTransportista,None)
	else:
		content = msgdic['content']
		# Averiguamos el tipo de la accion
		accion = gm.value(subject=content, predicate=RDF.type)

		#Llamada dinamica a la accion correspondiente
		if accion in actions:
			gr = actions[accion](gm)
		else:
			gr = create_notUnderstood(AgenteTransportista,None)

	return gr.serialize(format='xml')

@app.route("/verLotes")
def verLotes():
	lotes = g.subjects(predicate=RDF.type,object=lotes_ns.type)
	print(lotes)
	list = []
	for l in lotes:
		print("Lote:")
		print(l)
		d = lote_a_dict(g,l)
		list += [d]
	return render_template('listaLotes.html',list=list)

@app.route("/enviarLote")
def enviarLote():
	id = request.args['id']
	lote = grafoADict(g, lotes_ns[id])
	lote['envios'] = [] # Temporal, porque si esta vacio peta
	print("Lote:", lote)
	# Marcar pedidos como enviados
	g.set((lotes_ns[id], lotes_ns.Estadodellote, Literal("Enviado")))
	for s in lote['envios']:	# lote['envios'] contiene los ids de los envios
		g.set((s, envios_ns.Estadodelenvio, Literal("Enviado")))
	guardarGrafo()

	# TODO: Enviar factura al usuario

	return "Envio en curso"


''' Sempre s'ha de ficar el graf de la comunicacio com a parametre en un callback d'accio '''
def peticionOferta(graph):
	print("Callback working!")

	obj = createAction(AgenteTransportista,'respuestaOferta')
	gcom = Graph()

	gcom.add((obj,RDF.type,agn.EnviadorTestCallback))

	msg = build_message(gcom,
		perf=ACL.request,
		sender=AgenteTransportista.uri,
		content=obj)

	# Enviamos el mensaje a cualquier agente admisor
	print("Envio mensaje")
	send_message_any(msg,AgenteEnviador,DirectorioAgentes,enviador.type)

	return create_confirm(AgenteTransportista)

def registerActions():
	global actions
	actions[agn.TransportistaPeticionOferta] = peticionOferta

def guardarGrafo():
	g.serialize(graphFile,format="turtle")

@app.route("/")
def main_page():
	"""
	El hola mundo de los servicios web
	:return:
	"""
	return render_template('main.html')



def start_server():
	register_message(AgenteTransportista,DirectorioAgentes,transportista.type)
	registerActions()
	app.run(host=host,port=port,debug=True)

if __name__ == "__main__":
	start_server()
