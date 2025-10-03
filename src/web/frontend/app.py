# ARCHIVO: src/interfaz_web/app.py
import uuid

from reactpy import component, html, use_callback, use_context, use_effect, use_state
from reactpy_router import browser_router, route

from .api_client import get_api_client
from .features.dashboard.dashboard_components import DashboardControls, RobotDashboard
from .features.modals.dashboard_modal_components import AssignmentsModal, RobotEditModal, SchedulesModal
from .features.pools.pool_components import PoolsDashboard
from .hooks.use_debounced_value_hook import use_debounced_value
from .hooks.use_robots_hook import use_robots
from .shared.layout import AppLayout
from .shared.notifications import NotificationContext, ToastContainer


@component
def App():
    """
    Componente raíz que ahora gestiona qué controles se muestran en el Header
    dependiendo de la ruta actual.
    """
    notifications, set_notifications = use_state([])
    is_dark, set_is_dark = use_state(True)
    current_path, set_current_path = use_state("/")
    script_to_run, set_script_to_run = use_state(html._())

    @use_effect(dependencies=[is_dark])
    def apply_theme():
        theme = "dark" if is_dark else "light"
        key = f"theme-script-{uuid.uuid4()}"
        js_code = f"document.documentElement.setAttribute('data-theme', '{theme}')"
        set_script_to_run(html.script({"key": key}, js_code))

    def show_notification(message, style="success"):
        new_id = str(uuid.uuid4())
        set_notifications(lambda old: old + [{"id": new_id, "message": message, "style": style}])

    def dismiss_notification(notification_id):
        set_notifications(lambda old: [n for n in old if n["id"] != notification_id])

    context_value = {
        "notifications": notifications,
        "show_notification": show_notification,
        "dismiss_notification": dismiss_notification,
    }

    @component
    def DashboardWithRouting():
        set_current_path("/")
        # Hook con la lógica de datos principal
        robots_state = use_robots()
        filters = robots_state["filters"]
        set_filters = robots_state["set_filters"]

        # <<-- ESTADO "LEVANTADO" -->>
        # El estado para los modales ahora vive aquí, en el componente padre.
        selected_robot, set_selected_robot = use_state(None)
        modal_view, set_modal_view = use_state(None)

        # <<-- MANEJADORES DE ESTADO "LEVANTADOS" -->>
        def handle_modal_close(event=None):
            set_selected_robot(None)
            set_modal_view(None)

        async def handle_save_and_refresh():
            await robots_state["refresh"]()
            handle_modal_close()

        def handle_create_robot(event=None):  # Acepta el evento para evitar el TypeError
            set_selected_robot({})  # Objeto vacío para modo creación
            set_modal_view("edit")

        @use_callback
        async def handle_robot_action(action: str, robot):
            if action in ["toggle_active", "toggle_online"]:
                await robots_state["update_robot_status"](
                    robot["RobotId"],
                    {"Activo" if action == "toggle_active" else "EsOnline": not robot["Activo" if action == "toggle_active" else "EsOnline"]},
                )
            else:
                set_selected_robot(robot)
                set_modal_view(action)

        # Lógica de UI para los controles (sincronización y filtros)
        is_syncing, set_is_syncing = use_state(False)
        api_client = get_api_client()
        search_term, set_search_term = use_state(filters.get("name") or "")
        debounced_search = use_debounced_value(search_term, 300)
        is_searching = debounced_search != search_term

        @use_effect(dependencies=[debounced_search])
        def sync_search_with_hook():
            set_filters(lambda prev_filters: {**prev_filters, "name": debounced_search or None})

        @use_callback
        async def handle_sync(event=None):
            if is_syncing:
                return
            set_is_syncing(True)
            show_notification("Iniciando sincronización con A360...", "info")
            try:
                summary = await api_client.trigger_sync()
                show_notification(
                    f"Sincronización completa. Robots: {summary['robots_sincronizados']}, Equipos: {summary['equipos_sincronizados']}.", "success"
                )
                await robots_state["refresh"]()
            except Exception as e:
                show_notification(f"Error en la sincronización: {e}", "error")
            finally:
                set_is_syncing(False)

        # Pasamos los estados y manejadores a los componentes correspondientes
        controls = DashboardControls(
            is_syncing=is_syncing,
            on_sync=handle_sync,
            on_create_robot=handle_create_robot,
            search_term=search_term,
            on_search_change=set_search_term,
            active_filter="all" if filters.get("active") is None else str(filters.get("active")).lower(),
            on_active_change=lambda value: set_filters(lambda p: {**p, "active": None if value == "all" else value == "true"}),
            online_filter="all" if filters.get("online") is None else str(filters.get("online")).lower(),
            on_online_change=lambda value: set_filters(lambda p: {**p, "online": None if value == "all" else value == "true"}),
            is_searching=is_searching,
        )

        return AppLayout(
            theme_is_dark=is_dark,
            on_theme_toggle=set_is_dark,
            current_path=current_path,
            page_controls=controls,
            children=[
                # El RobotDashboard ahora solo se encarga de mostrar la tabla
                RobotDashboard(robots_state=robots_state, on_action=handle_robot_action),
                # <<-- LOS MODALES SE RENDERIZAN AQUÍ -->>
                RobotEditModal(
                    robot=selected_robot if modal_view == "edit" else None, on_close=handle_modal_close, on_save_success=handle_save_and_refresh
                ),
                AssignmentsModal(
                    robot=selected_robot if modal_view == "assign" else None, on_close=handle_modal_close, on_save_success=handle_save_and_refresh
                ),
                SchedulesModal(
                    robot=selected_robot if modal_view == "schedule" else None, on_close=handle_modal_close, on_save_success=handle_save_and_refresh
                ),
            ],
        )

    @component
    def PoolsWithRouting():
        set_current_path("/pools")
        return AppLayout(theme_is_dark=is_dark, on_theme_toggle=set_is_dark, current_path=current_path, children=[PoolsDashboard()])

    @component
    def NotFoundWithRouting():
        set_current_path("/404")
        return AppLayout(
            theme_is_dark=is_dark, on_theme_toggle=set_is_dark, current_path=current_path, children=[html.h1("Página no encontrada (404)")]
        )

    return NotificationContext(
        html._(
            script_to_run,
            browser_router(route("/", DashboardWithRouting()), route("/pools", PoolsWithRouting()), route("{404:any}", NotFoundWithRouting())),
            ToastContainer(),
        ),
        value=context_value,
    )


head = html.head(
    html.title("SAM"),
    html.meta({"charset": "utf-8"}),
    html.meta({"name": "viewport", "content": "width=device-width, initial-scale=1"}),
    html.link({"rel": "stylesheet", "href": "/static/css/pico.violet.min.css"}),
    html.link({"rel": "stylesheet", "href": "https://cdn.jsdelivr.net/npm/@picocss/pico@2.1.1/css/pico.colors.min.css"}),
    html.link({"rel": "stylesheet", "href": "/static/css/all.min.css"}),
    html.link({"href": "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined", "rel": "stylesheet"}),
    html.link({"rel": "stylesheet", "href": "/static/custom.css"}),
)
