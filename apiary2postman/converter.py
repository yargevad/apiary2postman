import json
from sys import stdout, stderr
from uuid import uuid4
from time import time
import urllib

from urimagic import URITemplate


def first_collection(json_obj):
	environment = createEnvironment(json_obj)

	# Create the collection
	collections = parseResourceGroups(
		json_obj['resourceGroups'], 
		environment['values'], 
		True)

	result = {
		'id' : str(uuid4()),
		'name' : json_obj['name'],
		'description' : json_obj['description'],
	  'timestamp' : int(time()),
	  'remote_id' : 0,
	  'synced' : False,
	  'order' : [],
	  'folders' : [],
	  'requests' : [],
	}

	for collection in collections:
		result['id'] = collection['id']
		result['folders'] += collection['folders']
		result['requests'] += collection['requests']

	return result

def full_response(json_obj):
	# Create the Environment
	environment = createEnvironment(json_obj)

	# Create the Header
	result = {
		'version' : 1,
		'globals' : [],
		'headerPresets' : [],
		'environments' : [ environment ],
	}

	# Create the collection
	result['collections'] = parseResourceGroups(
		json_obj['resourceGroups'], 
		result['environments'][0]['values'], 
		False)

	return result

def filter_collections(obj, exclude):
	new = []
	exclude = [x.lower() for x in exclude]
	for key in obj.iterkeys():
		if key == 'collections':
			for coll in obj[key]:
				append = True
				for ex in exclude:
					if ex in coll['name'].lower():
						append = False
				if append:
					new.append(coll)
			obj[key] = new
			break

def combine_collections(obj, name):
	# One top-level collection
	# Each previously top-level collection becomes a folder
	# The folders are discarded, after linking their requests into the new folder
	for key in obj.iterkeys():
		if key == 'collections':
			obj[key] = [_reorgCollections(obj[key], name)]

def _folderFromCollection(c):
	return {
			'name': c['name'],
			'id': str(uuid4()),
			'description': c['description'],
			'order': [],
			'collection_id': c['id'],
			'collection_name': c['name'],
	}

def _reorgCollections(colls, name):
	top = {
		'name': name,
		'id': str(uuid4()),
		'folders': [],
		'requests': [],
		'description': '',
		'timestamp': 0,
		'remote_id': 0,
		'order': [],
		'synced': False,
	}
	for c in colls:
		f = _folderFromCollection(c)
		f['collection_id'] = top['id']
		f['collection_name'] = top['name']
		top['folders'].append(f)
		top['order'].append(f['id'])
		for r in c['requests']:
			# add requests to folder where r['collection_id'] == c['id']
			r['collectionId'] = top['id']
			r['folder'] = f['id']
			f['order'].append(r['id'])
			top['requests'].append(r)
	return top

def write(json_data, out=stdout, pretty=False):
	if pretty:
		json.dump(json_data, out, indent=2, separators=(',', ': '))
	else:
		json.dump(json_data, out)


def createEnvironment(json_obj):
	environment = dict()
	environment['id'] = str(uuid4())
	environment['name'] = json_obj['name']
	environment['timestamp'] = int(time())
	environment['synced'] = False
	environment['syncedFilename'] = ''
	environment['values'] = []

	
	for metadata in json_obj['metadata']:
		if metadata['name'] == "FORMAT":
			continue

		value = dict()
		value['name'] = metadata['name']
		value['key'] = metadata['name']
		value['value'] = metadata['value']
		value['type'] = 'text'
		environment['values'].append(value)

	return environment

def parseResourceGroups(resourceGroups, environment_vals, only_collection):
	out = []
	for resourceGroup in resourceGroups:
		collection = dict()
		collection['id'] = str(uuid4());
		collection['folders'] = []
		collection['requests'] = []
		collection['name'] = resourceGroup['name']
		collection['description'] = resourceGroup['description']
		collection['timestamp'] = int(time())
		collection['synced'] = False
		collection['remote_id'] = 0
		collection['order'] = []

		for resource in resourceGroup['resources']:		
			folder = dict()
			folder['id'] = str(uuid4())
			folder['name'] = resource['name']
			folder['description'] = resource['description']
			folder['order'] = []
			folder['collection_id'] = collection['id']
			folder['collection_name'] = collection['name']	
		
			sub_url = URITemplate(resource['uriTemplate'])
			for action in resource['actions']:
				request = dict()
				request['id'] = str(uuid4())
				request['folder'] = folder['id']
				request['version'] = 2
				request['name'] = action['name']
				request['description'] = action['description']
				request['descriptionFormat'] = 'html'
				request['method'] = action['method']

                                params = {p['name']: p['example'] for p in action['parameters']}
                                sub_url_str = urllib.unquote(sub_url.expand(**params).string).encode('utf8')
				request['url'] = "{{HOST}}"+sub_url_str
				if only_collection:
					for value in environment_vals:
						if value['name'] == 'HOST':
							request['url'] = value['value'] + sub_url_str

				request['dataMode'] = 'params'
				request['data'] = []

				# Unsupported data				
				request['pathVariables'] = dict()
				request['tests'] = ''
				request['time'] = int(time())
				request['responses'] = []
				request['synced'] = False

				headers = {} 

				for example in action['examples']:
					# Add Headers
					for request_ex in example['requests']:
                                                headers.update({h['name']: h['value'] for h in request_ex['headers']})

						if len(request_ex['body']) > 0:
							request['dataMode'] = 'raw'
							request['data'] = request_ex['body']

					# Add Accept header to request based on response model (hack?)
                                        # EQD: This is not strictly correct since only 1 Accept header will appear in headers
					for response in example['responses']:
                                                content_types = [r['value'] for r in response['headers'] if r['name'].lower() == 'content-type']
                                                if len(content_types) > 0 and 'Accept' not in headers:
                                                    headers['Accept'] = content_types[0]
                                request['headers'] = '\n'.join(['%s: %s' % (k, v) for k,v in headers.iteritems()])
				# Add reference to collection to this request
				# The collectionId field refers to the parent collection, not the folder
				request['collectionId'] = collection['id']
				# Add reference to the request to the current folder
				folder['order'].append( request['id'] )
				# Add request json to the collection
				collection['requests'].append(request)

			# Add folder json to collection
			collection['folders'].append( folder )
		out.append(collection)
	return out
