# Qué rompería el pago de comisiones 

El pago de comisiones pude ser roto porque el partner devuelve los datos de los
leads con la trazabilidad rota , imaginemos que como en el ejemplo que se hizo en el
demo llegan clientes con un id creator vacío, esto si se deja así rompería la
trazabilidad de las comisiones dado que , a quien se le van a dar las comisiones si el lead
que cerró el trato no tiene ninguno asociado?.
Como un plus, pensé en organizarlos en una tabla donde hay diferentes status según que es lo faltante
en lo que envía el partner y el sistema intenta bucar coincidencias en nuestra pool de clientes
para lo cual con el factor humano se puede intentar hacer match y recuperar la trazabilidad,
se tiene la herramienta de poder ver que clientes entraron y que fue lo que devolvió el partner para recuperar
datos que se pudieron haber perdido. Si el sistema no encuentra match alguno también lo informa y lo eleva
para que no se dé por descartado y la comisión no se pierda sino que el factor humano pueda recuperarla

En general aquello que rompe la trazabilidad de comision es el fallo en los datos de manera que no se puedan
cruzar los datos y verificarlos en el sistema , para lo cual también se implementó un manejo de errores

