# ARCHIVO: src/web/frontend/app.py
import uuid

from reactpy import component, event, html, use_effect, use_state
from reactpy_router import browser_router, route

# Importamos los componentes de la UI
from .features.dashboard.dashboard_components import DashboardControls, RobotDashboard

# Modales
from .features.modals.dashboard_modal_components import AssignmentsModal, RobotEditModal, SchedulesModal
from .features.modals.pool_modals import PoolAssignmentsModal, PoolEditModal
from .features.pools.pool_components import PoolsControls, PoolsDashboard
from .hooks.use_debounced_value_hook import use_debounced_value
from .hooks.use_pools_hook import use_pools_management
from .hooks.use_robots_hook import use_robots
from .shared.common_components import ConfirmationModal
from .shared.layout import AppLayout
from .shared.notifications import NotificationContext, ToastContainer


@component
def App():
    """
    Componente raíz de la aplicación ReactPy.
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
        robots_state = use_robots()

        search_input, set_search_input = use_state(robots_state["filters"].get("name") or "")
        debounced_search = use_debounced_value(search_input, 300)

        @use_effect(dependencies=[debounced_search])
        def sync_search_with_filters():
            robots_state["set_filters"](lambda prev_filters: {**prev_filters, "name": debounced_search or None})

        is_searching = debounced_search != search_input

        selected_robot, set_selected_robot = use_state(None)
        modal_view, set_modal_view = use_state(None)

        def handle_modal_close(event=None):
            set_selected_robot(None)
            set_modal_view(None)

        async def handle_save_and_refresh():
            await robots_state["refresh"]()
            handle_modal_close()

        def handle_create_robot(event=None):
            set_selected_robot({})
            set_modal_view("edit")

        async def handle_robot_action(action: str, robot):
            if action in ["toggle_active", "toggle_online"]:
                status_key = "Activo" if action == "toggle_active" else "EsOnline"
                await robots_state["update_robot_status"](robot["RobotId"], {status_key: not robot[status_key]})
            else:
                set_selected_robot(robot)
                if action == "edit":
                    set_modal_view("edit")
                elif action == "assign":
                    set_modal_view("assign")
                elif action == "schedule":
                    set_modal_view("schedule")

        page_controls = DashboardControls(
            is_syncing=robots_state["is_syncing"],
            on_sync=robots_state["trigger_sync"],
            on_create_robot=handle_create_robot,
            search_term=search_input,
            on_search_change=set_search_input,
            active_filter="all"
            if robots_state["filters"].get("active") is None
            else str(robots_state["filters"].get("active")).lower(),
            on_active_change=lambda value: robots_state["set_filters"](
                lambda prev: {**prev, "active": None if value == "all" else value == "true"}
            ),
            online_filter="all"
            if robots_state["filters"].get("online") is None
            else str(robots_state["filters"].get("online")).lower(),
            on_online_change=lambda value: robots_state["set_filters"](
                lambda prev: {**prev, "online": None if value == "all" else value == "true"}
            ),
            is_searching=is_searching,
        )

        return html._(
            page_controls,
            RobotDashboard(
                robots=robots_state["robots"],
                on_action=handle_robot_action,  # Se pasa la corutina directamente
                robots_state=robots_state,
                set_current_page=robots_state["set_current_page"],
            ),
            RobotEditModal(
                robot=selected_robot if modal_view == "edit" else None,
                on_close=handle_modal_close,
                on_save_success=handle_save_and_refresh,
            ),
            AssignmentsModal(
                robot=selected_robot if modal_view == "assign" else None,
                on_close=handle_modal_close,
                on_save_success=handle_save_and_refresh,
            ),
            SchedulesModal(
                robot=selected_robot if modal_view == "schedule" else None,
                on_close=handle_modal_close,
                on_save_success=handle_save_and_refresh,
            ),
        )

    @component
    def PoolsWithRouting():
        set_current_path("/pools")
        pools_state = use_pools_management()
        modal_pool, set_modal_pool = use_state(None)
        modal_view, set_modal_view = use_state(None)
        pool_to_delete, set_pool_to_delete = use_state(None)

        def handle_modal_close(event=None):
            set_modal_pool(None)
            set_modal_view(None)
            set_pool_to_delete(None)

        def handle_create_click(event=None):
            set_modal_pool({})
            set_modal_view("edit")

        def handle_edit_click(pool):
            set_modal_pool(pool)
            set_modal_view("edit")

        def handle_assign_click(pool):
            set_modal_pool(pool)
            set_modal_view("assign")

        def handle_delete_click(pool):
            set_pool_to_delete(pool)

        async def handle_confirm_delete():
            if pool_to_delete:
                await pools_state["remove_pool"](pool_to_delete["PoolId"])
                handle_modal_close()

        async def handle_save_pool(pool_data):
            if pool_data.get("PoolId"):
                await pools_state["edit_pool"](pool_data["PoolId"], pool_data)
            else:
                await pools_state["add_pool"](pool_data)
            handle_modal_close()

        page_controls = PoolsControls(on_create_pool=handle_create_click)

        return html._(
            page_controls,
            PoolsDashboard(
                pools=pools_state["pools"],
                on_edit=handle_edit_click,
                on_assign=handle_assign_click,
                on_delete=handle_delete_click,
                loading=pools_state["loading"],
                error=pools_state["error"],
            ),
            PoolEditModal(
                pool=modal_pool if modal_view == "edit" else None, on_close=handle_modal_close, on_save=handle_save_pool
            ),
            PoolAssignmentsModal(
                pool=modal_pool if modal_view == "assign" else None,
                on_close=handle_modal_close,
                on_save_success=pools_state["refresh"],
            ),
            ConfirmationModal(
                is_open=bool(pool_to_delete),
                title="Confirmar Eliminación",
                message=f"¿Estás seguro de que quieres eliminar el pool '{pool_to_delete['Nombre'] if pool_to_delete else ''}'?",
                on_confirm=handle_confirm_delete,
                on_cancel=handle_modal_close,
            ),
        )

    @component
    def NotFoundWithRouting():
        set_current_path("/404")
        return html.h1("Página no encontrada (404)")

    return NotificationContext(
        html._(
            script_to_run,
            AppLayout(
                theme_is_dark=is_dark,
                on_theme_toggle=set_is_dark,
                current_path=current_path,
                children=[
                    browser_router(
                        route("/", DashboardWithRouting()),
                        route("/pools", PoolsWithRouting()),
                        route("{404:any}", NotFoundWithRouting()),
                    )
                ],
            ),
            ToastContainer(),
        ),
        value=context_value,
    )


# --- Elementos que inyectaremos en el <head> de la página ---
head = html.head(
    html.title("SAM"),
    html.meta({"charset": "utf-8"}),
    html.meta({"name": "viewport", "content": "width=device-width, initial-scale=1"}),
    html.link({"rel": "stylesheet", "href": "/static/css/pico.violet.min.css"}),
    html.link(
        {"rel": "stylesheet", "href": "https://cdn.jsdelivr.net/npm/@picocss/pico@2.1.1/css/pico.colors.min.css"}
    ),
    html.link({"rel": "stylesheet", "href": "/static/css/all.min.css"}),
    html.link({"rel": "stylesheet", "href": "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined"}),
    html.link({"rel": "stylesheet", "href": "/static/custom.css"}),
)
