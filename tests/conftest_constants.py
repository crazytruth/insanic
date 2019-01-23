ROUTES = (
    "",
    "/",
    "/{type}",
    "/{type}/",
    "/{type}/<{type}_arg>",
    "/{type}/<{type}_arg>/",
    "/{type}/<{type}_arg:int>",
    "/{type}/<{type}_arg:int>/",
    "/{type}/<{type}_arg:number>",
    "/{type}/<{type}_arg:number>/",
    "/{type}/<{type}:[A-z]+>",
    "/{type}/<{type}:[A-z]+>/",
    "/{type}/<{type}:[A-z0-9]{{0,4}}>",
    "/{type}/<{type}:[A-z0-9]{{0,4}}>/"
)
