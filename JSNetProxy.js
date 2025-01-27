
const _hostRegex = new RegExp( /(https?:\/\/[^/]+)/,"i");
window._replaceHost = function(str){
	if (! str)
		return str;
	if (window._ProxyAppendURL) {
		const encodedOrig = str;
		if (str.includes("?"))
			str +="&";
		else
			str +="?";
		str += "__OU=" + encodeURIComponent(encodedOrig);
	}

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

/*
For react you may run into an issue:
reactCont=reactCont.replace("(t.src=s.src)","(t.src=\"\"+(t.src??s.src))") # hacky but in certain conditions react will try to reset the source on something after it loads to re-trigger the load event but this breaks jsnetproxy.  This allows the same triggering but uses the existing source if it exists.  https://github.com/facebook/react/blob/37906d4dfbe80d71f312f7347bb9ddb930484d28/packages/react-dom-bindings/src/client/ReactFiberConfigDOM.js#L744

we could check it after load but thats a bit of a pita can't seem to override the src attribute to make it read only or anything.  we could copy it but if it needs the handle to it that would break it.
*/