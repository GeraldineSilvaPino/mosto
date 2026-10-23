-- MOSTO: funciones de transición y registro con identidad obtenida de auth.uid().
-- IMPORTANTE: plantilla para ADAPTAR y probar contra el esquema SQL REAL de Supabase.
-- Se asumieron nombres de tablas/columnas en minúscula, tal como PostgreSQL los
-- crea cuando no se utilizan identificadores entrecomillados.
-- Todas las funciones son SECURITY INVOKER y deben estar protegidas por RLS.
-- No instalar hasta comprobar columnas, CHECK, permisos y políticas en staging.

create or replace function public.mosto_atender_alerta(p_alerta_id bigint)
returns setof public.evento_alerta
language plpgsql security invoker set search_path = public
as $$
declare v_usuario_id bigint;
begin
  select u.id into v_usuario_id from public.usuario u
  join public.empresa_cliente e on e.id=u.empresa_id
  where u.auth_uid=auth.uid() and u.activo=true and e.activo=true;
  if v_usuario_id is null then raise exception 'Usuario no autorizado'; end if;
  return query
  update public.evento_alerta a
  set estado='atendida',atendida_por=v_usuario_id,fecha_atencion=now()
  where a.id=p_alerta_id and a.estado='pendiente'
  and exists (
    select 1 from public.proceso_fermentacion f
    join public.cuba c on c.id=f.cuba_id
    join public.usuario_bodega ub on ub.bodega_id=c.bodega_id and ub.usuario_id=v_usuario_id
    join public.rol r on r.id=ub.rol_id
    where f.id=a.fermentacion_id and r.codigo in ('ADMIN','OPERADOR','ENOLOGO')
  )
  returning a.*;
  if not found then raise exception 'Alerta inexistente, ya atendida o sin permiso'; end if;
end;$$;

create or replace function public.mosto_resolver_alerta(p_alerta_id bigint,p_nota text)
returns setof public.evento_alerta
language plpgsql security invoker set search_path=public
as $$
declare v_usuario_id bigint;
begin
  if trim(coalesce(p_nota,''))='' then raise exception 'Se requiere nota de resolución'; end if;
  select id into v_usuario_id from public.usuario where auth_uid=auth.uid() and activo=true;
  if v_usuario_id is null then raise exception 'Usuario no autorizado'; end if;
  return query update public.evento_alerta a
  set estado='resuelta',resolucion_nota=trim(p_nota)
  where a.id=p_alerta_id and a.estado='atendida'
  and exists (
    select 1 from public.proceso_fermentacion f
    join public.cuba c on c.id=f.cuba_id
    join public.usuario_bodega ub on ub.bodega_id=c.bodega_id and ub.usuario_id=v_usuario_id
    join public.rol r on r.id=ub.rol_id
    where f.id=a.fermentacion_id and r.codigo in ('ADMIN','OPERADOR','ENOLOGO')
  )
  returning a.*;
  if not found then raise exception 'La alerta debe estar atendida y ser accesible'; end if;
end;$$;

create or replace function public.mosto_registrar_intervencion(
  p_fermentacion_id bigint,p_tipo varchar,p_descripcion varchar,p_dosis varchar
)
returns setof public.bitacora_intervencion
language plpgsql security invoker set search_path=public
as $$
declare v_usuario_id bigint;
begin
  if trim(coalesce(p_tipo,''))='' or trim(coalesce(p_descripcion,''))='' or trim(coalesce(p_dosis,''))=''
  then raise exception 'Tipo, descripción y dosis son obligatorios'; end if;
  select id into v_usuario_id from public.usuario where auth_uid=auth.uid() and activo=true;
  if v_usuario_id is null then raise exception 'Usuario no autorizado'; end if;
  if not exists (
     select 1 from public.proceso_fermentacion f
     join public.cuba c on c.id=f.cuba_id
     join public.usuario_bodega ub on ub.bodega_id=c.bodega_id and ub.usuario_id=v_usuario_id
     join public.rol r on r.id=ub.rol_id
     where f.id=p_fermentacion_id and r.codigo in ('ADMIN','OPERADOR','ENOLOGO')
  ) then raise exception 'Sin permisos para esta fermentación'; end if;
  return query insert into public.bitacora_intervencion
    (fermentacion_id, usuario_id, fecha_registro,tipo_intervencion,descripcion,dosis_aplicada)
    values (p_fermentacion_id,v_usuario_id,now(),p_tipo,p_descripcion,p_dosis)
    returning *;
end;$$;

create or replace function public.mosto_cerrar_fermentacion(
  p_fermentacion_id bigint,p_estado varchar
)
returns setof public.proceso_fermentacion
language plpgsql security invoker set search_path=public
as $$
declare v_usuario_id bigint; v_cuba_id bigint;
begin
  if p_estado not in ('finalizada','detenida','cancelada') then raise exception 'Estado de cierre inválido'; end if;
  select id into v_usuario_id from public.usuario where auth_uid=auth.uid() and activo=true;
  if v_usuario_id is null then raise exception 'Usuario no autorizado'; end if;
  select f.cuba_id into v_cuba_id
  from public.proceso_fermentacion f join public.cuba c on c.id=f.cuba_id
  where f.id=p_fermentacion_id and f.estado='en curso'
  and exists(select 1 from public.usuario_bodega ub
    join public.rol r on r.id=ub.rol_id
    where ub.bodega_id=c.bodega_id and ub.usuario_id=v_usuario_id and r.codigo in ('ADMIN','OPERADOR','ENOLOGO'))
  for update of f;
  if v_cuba_id is null then raise exception 'Fermentación no disponible o sin permisos'; end if;
  -- PostgreSQL aplica ambas escrituras de forma atómica en la misma transacción.
  update public.cuba set estado_operativo='disponible' where id=v_cuba_id;
  return query update public.proceso_fermentacion f
  set estado=p_estado,fecha_real_fin=now() where f.id=p_fermentacion_id
  returning f.*;
end;$$;

create or replace function public.mosto_desasignar_dispositivo(p_asignacion_id bigint)
returns setof public.asignacion_dispositivo
language plpgsql security invoker set search_path=public
as $$
declare v_usuario_id bigint;
begin
  select id into v_usuario_id from public.usuario where auth_uid=auth.uid() and activo=true;
  return query update public.asignacion_dispositivo a
  set activo=false,desasignado_en=now()
  where a.id=p_asignacion_id and a.activo=true
    and exists(select 1 from public.cuba c
      join public.usuario_bodega ub on ub.bodega_id=c.bodega_id and ub.usuario_id=v_usuario_id
      join public.rol r on r.id=ub.rol_id
      where c.id=a.cuba_id and r.codigo in ('ADMIN','OPERADOR'))
  returning a.*;
  if not found then raise exception 'Asignación no activa o sin permisos'; end if;
end;$$;

revoke all on function public.mosto_atender_alerta(bigint) from public,anon;
revoke all on function public.mosto_resolver_alerta(bigint,text) from public,anon;
revoke all on function public.mosto_registrar_intervencion(bigint,varchar,varchar,varchar) from public,anon;
revoke all on function public.mosto_cerrar_fermentacion(bigint,varchar) from public,anon;
revoke all on function public.mosto_desasignar_dispositivo(bigint) from public,anon;
grant execute on function public.mosto_atender_alerta(bigint) to authenticated;
grant execute on function public.mosto_resolver_alerta(bigint,text) to authenticated;
grant execute on function public.mosto_registrar_intervencion(bigint,varchar,varchar,varchar) to authenticated;
grant execute on function public.mosto_cerrar_fermentacion(bigint,varchar) to authenticated;
grant execute on function public.mosto_desasignar_dispositivo(bigint) to authenticated;
