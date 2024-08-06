
const _hostRegex = new RegExp( /(https?:\/\/[^/]+)/,"i");

window._replaceHost = function(str){
	if (! str)
		return str;
	if (window._NoTilde)
		str = str.replace("~","_")
	return str.replace(_hostRegex,window._ProxyBase);
}
window.nv_XMLHttpRequest = new Proxy(XMLHttpRequest, {
	construct: function (target, args) {
		const originalRequest = new target();
		const prototypeDescriptors = Object.getOwnPropertyDescriptors(
			target.prototype
		)
		for (const propertyName in prototypeDescriptors) {
			Reflect.defineProperty(
				originalRequest,
				propertyName,
				prototypeDescriptors[propertyName]
			)
		}
		return new Proxy(originalRequest, {
			get: (target, name, trap) => {
				
				
				if (typeof target[name] === 'function') {
				  return (...args) => {
					switch (name) {
					  case 'open':
						if (args.length > 1)
							args[1] = window._replaceHost(args[1]);
						break;
		
					  default:
						break;
					}
		
					return target[name].apply(target, args);
				  }
				}
		
				
				return target[name];
			  },
			set: function (target, prop, value) {
				Reflect.set(target, prop, value) // or target[prop] = value
				return true;
			},
		})
	}
})

var oReq = new XMLHttpRequest();

window.nv_fetch = new Proxy(window.fetch, {
	apply: function (target, that, args) {
		if (args.length > 0 && args[0])
			if (typeof args[0] !== 'string' && args[0].url){
				const newUrl = window._replaceHost( args[0].url );
				if (newUrl != args[0].url)
					args[0] = new Request(newUrl, args[0]);
			}
			else
				args[0] = window._replaceHost(args[0].toString());
		return target.apply(that, args);
	},
});

window.XMLHttpRequest = window.nv_XMLHttpRequest;
window.fetch = window.nv_fetch;
window.oldAppendChild = Element.prototype.appendChild;
Element.prototype.appendChild = function() {
	if (arguments.length > 0) {
		if ( (arguments[0]?.tagName == "SCRIPT" || arguments[0]?.tagName == "IMG") && arguments[0].src)
			arguments[0].src = window._replaceHost(arguments[0].src);
		else if ( arguments[0]?.tagName == "DIV" && arguments[0].style?.backgroundImage?.startsWith("url"))
			arguments[0].style.backgroundImage = window._replaceHost(arguments[0].style?.backgroundImage);
	}
    return window.oldAppendChild.apply(this, arguments);
};

console.log("PROXY IN PLACE");