from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views import generic
from ..forms import UserSignUpForm
from ..mixins import MusicContextMixin

class CustomLoginView(MusicContextMixin, LoginView):
    template_name = 'music/login.html'

    def form_valid(self, form):
        messages.success(self.request, f"Witaj, ponownie, {form.get_user().username}!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Błędna nazwa użytkownika lub hasło.")
        response = super().form_invalid(form)
        response.status_code = 422
        return response

class CustomLogoutView(MusicContextMixin, LogoutView):
    def dispatch(self, request, *args, **kwargs):
        messages.info(request, "Zostałeś pomyślnie wylogowany. Do zobaczenia!")
        return super().dispatch(request, *args, **kwargs)

class SignUpView(MusicContextMixin, SuccessMessageMixin, generic.CreateView):
    form_class = UserSignUpForm
    success_url = reverse_lazy('music:home')
    template_name = 'music/signup.html'
    success_message = "Konto zostało pomyślnie utworzone! Zostałeś automatycznie zalogowany."

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        response.status_code = 422
        return response

class AccessDeniedView(MusicContextMixin, generic.TemplateView):
    """Widok informujący o wymaganym logowaniu do dostępu do strony."""
    template_name = 'music/access_denied.html'
