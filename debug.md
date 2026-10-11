# debug 1: TemplateResponse
template = self.get_template(name) 

getitem
rv = self._mapping[key]
~~~~~~~~~~~~~^^^^^
TypeError: unhashable type: 'dict'

Newer Starlette versions expect request as the first argument to TemplateResponse. Your old call passed "index.html" first and the context dict second. That made Starlette treat the dict as the template name, and the Jinja cache can't hash a dict, hence unhashable type: 'dict'.

The call is now **templates.TemplateResponse(request, "index.html")**. If you add template variables later, pass them as a third argument, for example {"foo": "bar"}.